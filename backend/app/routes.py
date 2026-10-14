import re, secrets, sqlite3
from functools import wraps
from flask import Blueprint, request, jsonify, session, render_template, g
from werkzeug.security import generate_password_hash, check_password_hash
from . import get_db

bp = Blueprint("main", __name__)

def user():
    uid = session.get("user_id")
    return get_db().execute("""SELECT u.*,r.name role FROM users u JOIN roles r ON r.id=u.role_id
                               WHERE u.id=? AND u.active=1""",(uid,)).fetchone() if uid else None

def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not user(): return jsonify(error="Authentication required"),401
        return f(*a, **kw)
    return w

def roles(*allowed):
    def deco(f):
        @wraps(f)
        def w(*a, **kw):
            u=user()
            if not u: return jsonify(error="Authentication required"),401
            if u["role"] not in allowed: return jsonify(error="Forbidden"),403
            return f(*a, **kw)
        return w
    return deco

def audit(action, entity="", entity_id=None, desc=""):
    u=user()
    get_db().execute("INSERT INTO audit_logs(user_id,action,entity,entity_id,description) VALUES(?,?,?,?,?)",
                     (u["id"] if u else None,action,entity,entity_id,desc))

@bp.route("/")
def index(): return render_template("index.html")
@bp.route("/login")
def login_page(): return render_template("login.html")
@bp.route("/register")
def register_page(): return render_template("register.html")
@bp.route("/dashboard")
@login_required
def dashboard(): return render_template("dashboard.html")
@bp.route("/staff")
@roles("STAFF","ADMIN")
def staff_page(): return render_template("staff.html")
@bp.route("/admin")
@roles("ADMIN")
def admin_page(): return render_template("admin.html")

@bp.get("/health")
def health():
    get_db().execute("SELECT 1")
    return jsonify(status="healthy",database="connected")

@bp.post("/api/auth/register")
def register():
    d=request.get_json() or {}
    required=["full_name","student_id","email","phone","password","confirm_password"]
    if any(not str(d.get(x,"")).strip() for x in required): return jsonify(error="All fields are required"),400
    if d["password"] != d["confirm_password"]: return jsonify(error="Passwords do not match"),400
    if not re.fullmatch(r"(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}",d["password"]):
        return jsonify(error="Password must be 8+ chars with upper, lower, number and special character"),400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",d["email"]): return jsonify(error="Invalid email"),400
    db=get_db()
    role=db.execute("SELECT id FROM roles WHERE name='STUDENT'").fetchone()[0]
    try:
        cur=db.execute("""INSERT INTO users(full_name,student_id,email,phone,password_hash,role_id,active)
                          VALUES(?,?,?,?,?,?,1)""",(d["full_name"],d["student_id"],d["email"],d["phone"],
                          generate_password_hash(d["password"]),role))
        audit("REGISTRATION","users",cur.lastrowid,"Student registered")
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback(); return jsonify(error="Email or Student ID already exists"),409
    return jsonify(message="Registration successful"),201

@bp.post("/api/auth/login")
def login():
    d=request.get_json() or {}
    u=get_db().execute("""SELECT u.*,r.name role FROM users u JOIN roles r ON r.id=u.role_id
                          WHERE lower(u.email)=lower(?) AND u.active=1""",(d.get("email",""),)).fetchone()
    if not u or not check_password_hash(u["password_hash"],d.get("password","")):
        return jsonify(error="Invalid credentials"),401
    session.clear(); session["user_id"]=u["id"]
    token=secrets.token_urlsafe(24); session["session_token"]=token
    db=get_db(); db.execute("UPDATE user_sessions SET active=0 WHERE user_id=? AND active=1",(u["id"],))
    db.execute("INSERT INTO user_sessions(user_id,session_token) VALUES(?,?)",(u["id"],token))
    audit("LOGIN","users",u["id"],"Successful login"); db.commit()
    return jsonify(id=u["id"],name=u["full_name"],role=u["role"])

@bp.post("/api/auth/logout")
@login_required
def logout():
    db=get_db(); db.execute("UPDATE user_sessions SET active=0,last_seen=CURRENT_TIMESTAMP WHERE session_token=?",(session.get("session_token"),))
    audit("LOGOUT","users",user()["id"],"Logout"); db.commit(); session.clear()
    return jsonify(message="Logged out")

@bp.get("/api/me")
@login_required
def me():
    u=user(); return jsonify(id=u["id"],name=u["full_name"],email=u["email"],role=u["role"])

@bp.post("/api/session/heartbeat")
@login_required
def heartbeat():
    db=get_db(); token=session.get("session_token")
    db.execute("UPDATE user_sessions SET last_seen=CURRENT_TIMESTAMP,active=1 WHERE session_token=? AND user_id=?",(token,user()["id"]))
    db.commit(); return jsonify(ok=True)

@bp.get("/api/menu")
def menu():
    rows=get_db().execute("""SELECT m.*,c.name category FROM menu_items m
                             JOIN menu_categories c ON c.id=m.category_id
                             WHERE m.availability=1 ORDER BY c.name,m.name""").fetchall()
    return jsonify(items=[dict(r) for r in rows])

@bp.get("/api/menu/highlights")
def menu_highlights():
    db=get_db()
    top=db.execute("""SELECT m.id,m.name,m.description,m.price,m.image,m.stock_quantity,m.preparation_time,
        COALESCE(SUM(oi.quantity),0) sold
        FROM menu_items m LEFT JOIN order_items oi ON oi.menu_item_id=m.id
        WHERE m.availability=1 GROUP BY m.id ORDER BY sold DESC,m.name LIMIT 6""").fetchall()
    instant=db.execute("""SELECT id,name,description,price,image,stock_quantity,preparation_time
        FROM menu_items WHERE availability=1 AND stock_quantity>0 AND preparation_time<=3
        ORDER BY preparation_time,stock_quantity DESC LIMIT 6""").fetchall()
    cats=db.execute("SELECT id,name FROM menu_categories ORDER BY name").fetchall()
    return jsonify(top_ordered=[dict(r) for r in top],instant_ready=[dict(r) for r in instant],categories=[dict(r) for r in cats])

def _kitchen_load(db, now=None):
    from datetime import datetime
    now = now or datetime.now()
    rows = db.execute("""SELECT estimated_minutes, estimated_ready_at, status
        FROM orders WHERE canteen_id=1 AND status IN ('ORDER_PLACED','ACCEPTED','PREPARING')
        ORDER BY id""").fetchall()
    remaining = []
    for row in rows:
        try:
            ready = datetime.strptime(row["estimated_ready_at"], "%Y-%m-%d %H:%M:%S")
            mins = max(0, int((ready-now).total_seconds()/60 + .999))
        except Exception:
            mins = max(1, int(row["estimated_minutes"] or 5))
        remaining.append(mins)
    # A single shared kitchen queue works in sequence; use the latest active order
    # deadline as the current queue drain point rather than adding overlapping ETAs.
    queue_minutes = max(remaining, default=0)
    return len(rows), queue_minutes

@bp.get("/api/pickup-slots")
@login_required
@roles("STUDENT")
def pickup_slots():
    from datetime import datetime, timedelta
    db=get_db()
    now=datetime.now().replace(second=0,microsecond=0)
    active_count, queue_minutes = _kitchen_load(db, now)
    earliest=now+timedelta(minutes=max(5, queue_minutes+5))
    # Round up to the next five-minute boundary, so nearby alternatives like
    # 12:30 and 12:35 are available when the kitchen can support them.
    earliest=earliest.replace(minute=(earliest.minute//5)*5)
    if earliest < now+timedelta(minutes=max(5, queue_minutes+5)):
        earliest += timedelta(minutes=5)
    slots=[{"value":"ASAP","label":f"Earliest available — about {earliest.strftime('%I:%M %p')}"}]
    for i in range(12):
        t=earliest+timedelta(minutes=5*i)
        value=t.strftime("%H:%M")
        slots.append({"value":value,"label":t.strftime("%I:%M %p") + (" · recommended" if i==0 else "")})
    return jsonify(slots=slots, active_orders=active_count, queue_minutes=queue_minutes,
                   earliest_available=earliest.strftime("%H:%M"), server_time=now.strftime("%H:%M"))

@bp.post("/api/orders")
@login_required
@roles("STUDENT")
def create_order():
    from datetime import datetime, timedelta
    d=request.get_json() or {}; items=d.get("items",[])
    if not items: return jsonify(error="Cart is empty"),400
    db=get_db(); u=user(); pickup=d.get("pickup_slot","ASAP")
    try:
        db.execute("BEGIN")
        total=0; prep=0; checked=[]
        for x in items:
            row=db.execute("SELECT * FROM menu_items WHERE id=? AND availability=1",(x.get("id"),)).fetchone()
            q=int(x.get("quantity",0))
            if not row or q<1 or q>row["stock_quantity"]: raise ValueError("Item unavailable or insufficient stock")
            total += row["price"]*q; prep=max(prep, int(row["preparation_time"] or 5)*q); checked.append((row,q))
        # Sequence-aware estimate: active kitchen queue drains first, then this
        # cart's preparation estimate. ETA is recalculated at checkout to avoid
        # promising a slot based on stale browser information.
        now=datetime.now()
        active_count, queue_minutes = _kitchen_load(db, now)
        estimated=max(5, queue_minutes + prep + (2 if active_count else 0))
        earliest_ready=now+timedelta(minutes=estimated)
        requested=None
        if pickup and pickup != "ASAP":
            try:
                requested=datetime.strptime(pickup, "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day, second=0, microsecond=0)
                if requested < now:
                    requested += timedelta(days=1)
            except ValueError:
                raise ValueError("Please select a valid pickup time.")
        # If staff cannot meet the requested time, shift to the nearest feasible
        # five-minute slot (e.g. 12:30 request becomes 12:35).
        if requested and requested < earliest_ready:
            ready_dt=earliest_ready.replace(second=0, microsecond=0)
            remainder=ready_dt.minute % 5
            if remainder:
                ready_dt += timedelta(minutes=5-remainder)
            if ready_dt < earliest_ready:
                ready_dt += timedelta(minutes=5)
            pickup_actual=ready_dt.strftime("%H:%M")
            estimated=max(5, int((ready_dt-now).total_seconds()/60 + .999))
        elif requested:
            ready_dt=requested
            pickup_actual=requested.strftime("%H:%M")
            estimated=max(5, int((ready_dt-now).total_seconds()/60 + .999))
        else:
            ready_dt=earliest_ready
            pickup_actual=ready_dt.strftime("%H:%M")
        ready_at=ready_dt.strftime("%Y-%m-%d %H:%M:%S")
        public=f"SC-{datetime.now().year}-{secrets.token_hex(3).upper()}"
        token=db.execute("SELECT COALESCE(MAX(token_number),100)+1 FROM orders WHERE canteen_id=1").fetchone()[0]
        cur=db.execute("""INSERT INTO orders(public_order_id,user_id,canteen_id,token_number,total,status,pickup_slot,estimated_minutes,estimated_ready_at)
                          VALUES(?,?,?,?,?,?,?,?,?)""",(public,u["id"],1,token,total,"ORDER_PLACED",pickup_actual,estimated,ready_at))
        oid=cur.lastrowid
        for row,q in checked:
            db.execute("INSERT INTO order_items(order_id,menu_item_id,quantity,unit_price) VALUES(?,?,?,?)",(oid,row["id"],q,row["price"]))
            db.execute("UPDATE menu_items SET stock_quantity=stock_quantity-? WHERE id=?",(q,row["id"]))
        db.execute("INSERT INTO queue(order_id,position,status) VALUES(?,?,?)",(oid,token-100,"WAITING"))
        db.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",(u["id"],"Order placed",f"Token #{token}. Estimated preparation time: {estimated} min. Pickup: {pickup_actual}."))
        # Notify all active staff/admin users that a new kitchen order arrived.
        staff_rows=db.execute("SELECT u.id FROM users u JOIN roles r ON r.id=u.role_id WHERE u.active=1 AND r.name IN ('STAFF','ADMIN')").fetchall()
        for staff in staff_rows:
            db.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",(staff["id"],"New kitchen order",f"Token #{token} from {u['full_name']} • {estimated} min estimated preparation time."))
        audit("ORDER_CREATED","orders",oid,public); db.commit()
    except Exception as e:
        db.rollback(); return jsonify(error=str(e)),400
    return jsonify(order_id=public,token=token,status="ORDER_PLACED",estimated_minutes=estimated,estimated_ready_at=ready_at,pickup_slot=pickup_actual,requested_pickup_slot=pickup,adjusted=bool(pickup and pickup != "ASAP" and pickup_actual != pickup)),201

@bp.get("/api/orders")
@login_required
def orders():
    u=user()
    rows=get_db().execute("""SELECT o.*, GROUP_CONCAT(m.name||' x'||oi.quantity, ', ') items
                             FROM orders o JOIN order_items oi ON oi.order_id=o.id
                             JOIN menu_items m ON m.id=oi.menu_item_id
                             WHERE o.user_id=? GROUP BY o.id ORDER BY o.id DESC""",(u["id"],)).fetchall()
    return jsonify(orders=[dict(r) for r in rows])

@bp.get("/api/queue/my-position")
@login_required
@roles("STUDENT")
def my_queue():
    u=user(); row=get_db().execute("""SELECT o.token_number,o.status,
        (SELECT COUNT(*) FROM orders p WHERE p.canteen_id=o.canteen_id AND p.id<o.id
         AND p.status IN ('ORDER_PLACED','ACCEPTED','PREPARING')) position
        FROM orders o WHERE o.user_id=? AND o.status NOT IN ('COLLECTED','CANCELLED')
        ORDER BY o.id DESC LIMIT 1""",(u["id"],)).fetchone()
    result=dict(row) if row else {}
    active=get_db().execute("SELECT COUNT(*) n FROM orders WHERE canteen_id=1 AND status IN ('ORDER_PLACED','ACCEPTED','PREPARING')").fetchone()["n"]
    result["active_orders"]=active
    return jsonify(result)

@bp.get("/api/notifications")
@login_required
def notifications():
    rows=get_db().execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 30",(user()["id"],)).fetchall()
    return jsonify(notifications=[dict(r) for r in rows])

@bp.put("/api/notifications/<int:nid>/read")
@login_required
def read_notification(nid):
    get_db().execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",(nid,user()["id"])); get_db().commit()
    return jsonify(message="Read")

@bp.post("/api/notifications/read-all")
@login_required
def read_all_notifications():
    get_db().execute("UPDATE notifications SET is_read=1 WHERE user_id=?",(user()["id"],)); get_db().commit()
    return jsonify(message="All notifications marked as read")

@bp.get("/api/staff/orders")
@roles("STAFF","ADMIN")
def staff_orders():
    rows=get_db().execute("""SELECT o.*,u.full_name student,
        GROUP_CONCAT(m.name||' x'||oi.quantity, ', ') items
        FROM orders o JOIN users u ON u.id=o.user_id JOIN order_items oi ON oi.order_id=o.id
        JOIN menu_items m ON m.id=oi.menu_item_id GROUP BY o.id ORDER BY o.id DESC""").fetchall()
    out=[]
    from datetime import datetime
    for r in rows:
        x=dict(r)
        if x.get("status") in ("ORDER_PLACED","ACCEPTED","PREPARING"):
            try:
                ready=datetime.strptime(x["estimated_ready_at"],"%Y-%m-%d %H:%M:%S")
                x["remaining_minutes"]=max(0,int((ready-datetime.now()).total_seconds()/60+0.999))
            except Exception: x["remaining_minutes"]=x.get("estimated_minutes") or 5
        else: x["remaining_minutes"]=0
        out.append(x)
    return jsonify(orders=out)

@bp.get("/api/staff/notifications")
@roles("STAFF","ADMIN")
def staff_notifications():
    rows=get_db().execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 30",(user()["id"],)).fetchall()
    return jsonify(notifications=[dict(r) for r in rows])


def _staff_eta_suggestion(oid):
    """Return a practical ETA based on this order's food prep plus current kitchen load."""
    from datetime import datetime
    db=get_db()
    row=db.execute("""SELECT o.id,o.estimated_minutes,o.status,
        COALESCE(SUM(oi.quantity * COALESCE(m.preparation_time,5)),0) item_prep
        FROM orders o
        JOIN order_items oi ON oi.order_id=o.id
        JOIN menu_items m ON m.id=oi.menu_item_id
        WHERE o.id=? GROUP BY o.id""",(oid,)).fetchone()
    if not row: return None
    active=db.execute("""SELECT id,estimated_minutes,estimated_ready_at FROM orders
        WHERE canteen_id=(SELECT canteen_id FROM orders WHERE id=?)
        AND status IN ('ORDER_PLACED','ACCEPTED','PREPARING') AND id<>?""",(oid,oid)).fetchall()
    workload=0
    for a in active:
        try:
            ready=datetime.strptime(a["estimated_ready_at"],"%Y-%m-%d %H:%M:%S")
            workload += max(0,int((ready-datetime.now()).total_seconds()/60+0.999))
        except Exception:
            workload += int(a["estimated_minutes"] or 5)
    queue_buffer=min(15,max(0,len(active)-1)*2)
    item_prep=max(5,int(row["item_prep"] or 5))
    suggested=max(5,item_prep + min(workload,30) + queue_buffer)
    return {"suggested_minutes":suggested,"item_prep_minutes":item_prep,
            "active_orders":len(active),"busy_buffer_minutes":queue_buffer}

@bp.get("/api/staff/orders/<int:oid>/eta-suggestion")
@roles("STAFF","ADMIN")
def eta_suggestion(oid):
    result=_staff_eta_suggestion(oid)
    if not result: return jsonify(error="Order not found"),404
    return jsonify(**result)

@bp.put("/api/staff/orders/<int:oid>/estimate")
@roles("STAFF","ADMIN")
def update_estimate(oid):
    from datetime import datetime, timedelta
    d=request.get_json() or {}
    try: minutes=int(d.get("estimated_minutes"))
    except (TypeError,ValueError): return jsonify(error="Enter a valid preparation time in minutes"),400
    if minutes < 1 or minutes > 240: return jsonify(error="Preparation time must be between 1 and 240 minutes"),400
    db=get_db(); row=db.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
    if not row: return jsonify(error="Order not found"),404
    ready=(datetime.now()+timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute("""UPDATE orders SET estimated_minutes=?,estimated_ready_at=?,
        assigned_staff_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (minutes,ready,user()["id"],oid))
    db.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",
        (row["user_id"],"Preparation time updated",
         f"Order {row['public_order_id']} has an updated estimated preparation time of {minutes} minutes."))
    audit("ETA_UPDATED","orders",oid,f"ETA set to {minutes} minutes by {user()['full_name']}")
    db.commit()
    return jsonify(message="Estimated time updated",estimated_minutes=minutes,estimated_ready_at=ready)

@bp.put("/api/staff/orders/<int:oid>/status")
@roles("STAFF","ADMIN")
def status(oid):
    d=request.get_json() or {}; new=d.get("status")
    allowed={"ORDER_PLACED":"ACCEPTED","ACCEPTED":"PREPARING","PREPARING":"READY","READY":"COLLECTED"}
    row=get_db().execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
    if not row or allowed.get(row["status"])!=new: return jsonify(error="Invalid status transition"),400
    db=get_db(); uid=user()["id"]
    eta=d.get("estimated_minutes")
    if eta is not None:
        try: eta=int(eta)
        except (TypeError,ValueError): return jsonify(error="Invalid estimated time"),400
        if eta < 1 or eta > 240: return jsonify(error="Estimated time must be 1-240 minutes"),400
        from datetime import datetime, timedelta
        ready=(datetime.now()+timedelta(minutes=eta)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE orders SET status=?,estimated_minutes=?,estimated_ready_at=?,assigned_staff_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (new,eta,ready,uid,oid))
    else:
        db.execute("UPDATE orders SET status=?, assigned_staff_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",(new,uid,oid))
    db.execute("UPDATE queue SET status=? WHERE order_id=?",(new,oid))
    current=db.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
    if new=="ACCEPTED": msg=f"Order {row['public_order_id']} accepted. Kitchen will start shortly. Estimated time: {current['estimated_minutes']} min."
    elif new=="PREPARING": msg=f"Order {row['public_order_id']} is being prepared. About {current['estimated_minutes']} min estimated from order placement."
    elif new=="READY": msg=f"Order {row['public_order_id']} is READY for pickup!"
    else: msg=f"Order {row['public_order_id']} is {new}."
    db.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",(row["user_id"],"Order update",msg))
    # Staff activity notification keeps the kitchen panel useful across staff accounts.
    staff_rows=db.execute("SELECT u.id FROM users u JOIN roles r ON r.id=u.role_id WHERE u.active=1 AND r.name IN ('STAFF','ADMIN') AND u.id!=?",(uid,)).fetchall()
    for sr in staff_rows:
        db.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",(sr["id"],"Kitchen update",f"Token #{row['token_number']} moved to {new.replace('_',' ')} by {user()['full_name']}."))
    audit("STATUS_CHANGED","orders",oid,f"{row['status']} -> {new}"); db.commit()
    return jsonify(message="Updated",estimated_minutes=current["estimated_minutes"],estimated_ready_at=current["estimated_ready_at"])

@bp.post("/api/staff/orders/<int:oid>/verify")
@roles("STAFF","ADMIN")
def verify(oid):
    row=get_db().execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
    if not row or row["status"]!="READY": return jsonify(error="Order is not ready"),400
    db=get_db(); db.execute("UPDATE orders SET status='COLLECTED', assigned_staff_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",(user()["id"],oid) )
    db.execute("UPDATE queue SET status='COLLECTED' WHERE order_id=?",(oid,))
    db.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",
               (row["user_id"],"Order collected",f"Token #{row['token_number']} has been collected. Thank you and enjoy your meal!"))
    staff_rows=db.execute("SELECT u.id FROM users u JOIN roles r ON r.id=u.role_id WHERE u.active=1 AND r.name IN ('STAFF','ADMIN') AND u.id!=?",(user()["id"],)).fetchall()
    for sr in staff_rows:
        db.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",
                   (sr["id"],"Order collected",f"Token #{row['token_number']} was collected by {user()['full_name']}."))
    audit("QR_VERIFIED","orders",oid,"QR/order verification completed"); db.commit()
    return jsonify(message="Collected")

@bp.get("/api/admin/online-users")
@roles("ADMIN")
def online_users():
    rows=get_db().execute("""SELECT u.full_name,u.student_id,u.email,r.name role,s.login_at,s.last_seen
      FROM user_sessions s JOIN users u ON u.id=s.user_id JOIN roles r ON r.id=u.role_id
      WHERE s.active=1 AND s.last_seen >= datetime('now','-2 minutes') ORDER BY s.last_seen DESC""").fetchall()
    return jsonify(users=[dict(r) for r in rows])

@bp.get("/api/admin/staff-activity")
@roles("ADMIN")
def staff_activity():
    rows=get_db().execute("""SELECT u.id,u.full_name,u.student_id,u.email,
      COUNT(DISTINCT CASE WHEN o.status NOT IN ('COLLECTED','CANCELLED') THEN o.id END) active_orders,
      COUNT(DISTINCT o.id) total_orders,MAX(o.updated_at) last_activity
      FROM users u JOIN roles r ON r.id=u.role_id LEFT JOIN orders o ON o.assigned_staff_id=u.id
      WHERE r.name='STAFF' GROUP BY u.id ORDER BY active_orders DESC,total_orders DESC""").fetchall()
    return jsonify(staff=[dict(r) for r in rows])

@bp.get("/api/admin/orders")
@roles("ADMIN")
def admin_orders():
    rows=get_db().execute("""SELECT o.id,o.public_order_id,o.token_number,o.total,o.status,o.created_at,o.updated_at,
      u.full_name student,s.full_name staff,GROUP_CONCAT(m.name||' x'||oi.quantity, ', ') items
      FROM orders o JOIN users u ON u.id=o.user_id JOIN order_items oi ON oi.order_id=o.id JOIN menu_items m ON m.id=oi.menu_item_id
      LEFT JOIN users s ON s.id=o.assigned_staff_id GROUP BY o.id ORDER BY o.id DESC""").fetchall()
    return jsonify(orders=[dict(r) for r in rows])

@bp.get("/api/admin/analytics")
@roles("ADMIN")
def analytics():
    db=get_db()
    total=db.execute("SELECT COUNT(*) FROM users WHERE role_id=(SELECT id FROM roles WHERE name='STUDENT')").fetchone()[0]
    orders=db.execute("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')").fetchone()[0]
    revenue=db.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE date(created_at)=date('now') AND status!='CANCELLED'").fetchone()[0]
    return jsonify(students=total,today_orders=orders,revenue=revenue,active_queue=db.execute("SELECT COUNT(*) FROM queue WHERE status NOT IN ('COLLECTED','CANCELLED')").fetchone()[0])

@bp.get("/api/admin/audit-logs")
@roles("ADMIN")
def logs():
    rows=get_db().execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify(logs=[dict(r) for r in rows])
