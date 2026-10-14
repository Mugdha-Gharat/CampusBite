import os, sqlite3
from flask import Flask, g
from werkzeug.security import generate_password_hash
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(BASE, "database", "database.db")
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db
def create_app():
    app = Flask(__name__, template_folder=os.path.join(BASE,"frontend","templates"), static_folder=os.path.join(BASE,"frontend","static"))
    app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=2*1024*1024)
    from .routes import bp
    app.register_blueprint(bp)
    @app.teardown_appcontext
    def close_db(exc=None):
        db = g.pop("db", None)
        if db: db.close()
    init_db(app)
    return app
def init_db(app):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    db=sqlite3.connect(DB); db.execute("PRAGMA foreign_keys=ON")
    schema=open(os.path.join(BASE,"database","schema.sql"),encoding="utf-8").read()
    db.executescript(schema)
    # Upgrade databases created by older versions.
    cols={r[1] for r in db.execute("PRAGMA table_info(orders)").fetchall()}
    if "assigned_staff_id" not in cols: db.execute("ALTER TABLE orders ADD COLUMN assigned_staff_id INTEGER")
    if "updated_at" not in cols: db.execute("ALTER TABLE orders ADD COLUMN updated_at TEXT")
    if "estimated_minutes" not in cols: db.execute("ALTER TABLE orders ADD COLUMN estimated_minutes INTEGER DEFAULT 5")
    if "estimated_ready_at" not in cols: db.execute("ALTER TABLE orders ADD COLUMN estimated_ready_at TEXT")
    db.execute("CREATE INDEX IF NOT EXISTS idx_orders_staff ON orders(assigned_staff_id)")
    db.execute("CREATE TABLE IF NOT EXISTS user_sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,session_token TEXT UNIQUE NOT NULL,login_at TEXT DEFAULT CURRENT_TIMESTAMP,last_seen TEXT DEFAULT CURRENT_TIMESTAMP,active INTEGER DEFAULT 1,FOREIGN KEY(user_id) REFERENCES users(id))")
    for role_name in ("STUDENT","STAFF","ADMIN"):
        db.execute("INSERT OR IGNORE INTO roles(name) VALUES (?)",(role_name,))
    roles={r[0]:r[1] for r in db.execute("SELECT name,id FROM roles")}
    demo=[("Mugdha","23CSE101","mugdha@example.com","9999999999","Student@123","STUDENT"),("Canteen Staff","STAFF001","staff@example.com","9999999998","Staff@123","STAFF"),("System Admin","ADMIN001","admin@example.com","9999999997","Admin@123","ADMIN")]
    for n,sid,email,phone,pw,role in demo:
        ex=db.execute("SELECT id FROM users WHERE lower(email)=lower(?)",(email,)).fetchone()
        if not ex:
            # Keep existing demo users in older bundled databases in sync when their
            # demo email/name was changed (e.g. Vrushali -> Mugdha).
            ex=db.execute("SELECT id FROM users WHERE lower(full_name)=lower(?)",(n,)).fetchone()
        if ex:
            db.execute("UPDATE users SET full_name=?,student_id=?,email=?,phone=?,password_hash=?,role_id=?,active=1 WHERE id=?",(n,sid,email,phone,generate_password_hash(pw),roles[role],ex[0]))
        else:
            db.execute("INSERT INTO users(full_name,student_id,email,phone,password_hash,role_id,active) VALUES(?,?,?,?,?,?,1)",(n,sid,email,phone,generate_password_hash(pw),roles[role]))
    if db.execute("SELECT COUNT(*) FROM canteens").fetchone()[0]==0: db.execute("INSERT INTO canteens(name,location,active) VALUES('Main College Canteen','Campus',1)")
    for cat in ("Meals","Snacks","Beverages","Breakfast","South Indian","Fast Food","Desserts"):
        db.execute("INSERT OR IGNORE INTO menu_categories(name) VALUES(?)",(cat,))
    cat_ids={r[0]:r[1] for r in db.execute("SELECT name,id FROM menu_categories")}
    menu=[
      ("Veg Thali","Meals","Complete vegetarian meal with dal, sabzi, roti and rice",70,"https://images.unsplash.com/photo-1601050690117-94f5f6fa8bd7?auto=format&fit=crop&w=700&q=80",10),
      ("Paneer Butter Masala","Meals","Creamy paneer curry with rich Indian spices",95,"https://images.unsplash.com/photo-1631452180519-c014fe946bc7?auto=format&fit=crop&w=700&q=80",12),
      ("Veg Biryani","Meals","Fragrant basmati rice with vegetables and spices",80,"https://images.unsplash.com/photo-1563379091339-03246963d51a?auto=format&fit=crop&w=700&q=80",12),
      ("Rajma Rice","Meals","Comforting rajma curry served with steamed rice",65,"https://images.unsplash.com/photo-1585937421612-70a008356fbe?auto=format&fit=crop&w=700&q=80",10),
      ("Masala Dosa","South Indian","Crispy dosa with spiced potato filling and chutney",60,"https://images.unsplash.com/photo-1668236543090-82eba5ee5976?auto=format&fit=crop&w=700&q=80",8),
      ("Idli Sambar","Breakfast","Soft idlis with hot sambar and chutney",45,"https://images.unsplash.com/photo-1589302168068-964664d93dc0?auto=format&fit=crop&w=700&q=80",6),
      ("Vada Pav","Fast Food","Mumbai-style potato fritter pav with chutneys",30,"https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=700&q=80",5),
      ("Paneer Roll","Fast Food","Grilled paneer wrap with fresh vegetables",75,"https://images.unsplash.com/photo-1626700051175-6818013e1d4f?auto=format&fit=crop&w=700&q=80",7),
      ("Veg Burger","Fast Food","Crispy veg patty, lettuce, cheese and sauce",65,"https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=700&q=80",8),
      ("Veg Pizza","Fast Food","Cheesy pizza topped with fresh vegetables",110,"https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=700&q=80",15),
      ("Masala Sandwich","Fast Food","Fresh grilled sandwich with spicy filling",50,"https://images.unsplash.com/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=700&q=80",6),
      ("Samosa","Snacks","Crispy potato and pea snack",20,"https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=700&q=80",3),
      ("French Fries","Snacks","Crispy salted fries served hot",55,"https://images.unsplash.com/photo-1573080496219-bb080dd4f877?auto=format&fit=crop&w=700&q=80",5),
      ("Veg Momos","Snacks","Steamed vegetable momos with spicy dip",60,"https://images.unsplash.com/photo-1625220194771-7ebdea0b70b9?auto=format&fit=crop&w=700&q=80",8),
      ("Masala Chai","Beverages","Hot Indian tea with aromatic spices",15,"https://images.unsplash.com/photo-1594631252845-29fc4cc8cde9?auto=format&fit=crop&w=700&q=80",3),
      ("Cold Coffee","Beverages","Chilled creamy coffee",45,"https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=700&q=80",5),
      ("Fresh Lime Soda","Beverages","Refreshing sweet and salty lime soda",30,"https://images.unsplash.com/photo-1556679343-c7306c1976bc?auto=format&fit=crop&w=700&q=80",3),
      ("Mango Shake","Beverages","Creamy seasonal mango shake",55,"https://images.unsplash.com/photo-1623065422902-30a2d299bbe4?auto=format&fit=crop&w=700&q=80",5),
      ("Chocolate Cake","Desserts","Soft chocolate cake slice",55,"https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=700&q=80",5),
      ("Gulab Jamun","Desserts","Warm syrup-soaked Indian sweet",35,"https://images.unsplash.com/photo-1666190094762-8c5c6a1e0a2f?auto=format&fit=crop&w=700&q=80",4),
    ]
    for name,cat,desc,price,img,prep in menu:
        exists=db.execute("SELECT id FROM menu_items WHERE lower(name)=lower(?)",(name,)).fetchone()
        if exists:
            db.execute("UPDATE menu_items SET description=?,price=?,image=?,availability=1,preparation_time=? WHERE id=?",(desc,price,img,prep,exists[0]))
        else:
            db.execute("INSERT INTO menu_items(canteen_id,category_id,name,description,price,image,availability,stock_quantity,preparation_time) VALUES(?,?,?,?,?,?,?,?,?)",(1,cat_ids[cat],name,desc,price,img,1,50 if prep>5 else 100,prep))
    db.commit(); db.close()
