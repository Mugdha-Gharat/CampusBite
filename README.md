# Smart Canteen — Pre-Order & Digital Queue Management System

A VS Code-ready web application built with **HTML, CSS, vanilla JavaScript, Python (Flask), and SQL (SQLite for local development)**. Docker packaging, GitHub Actions CI, and Kubernetes manifests are included. It is intended as a college project/demo and can be extended to a managed database for production.

## Features

- Student registration and login with password hashing and role-based access.
- Student menu with categories, search, highlights, cart/order placement, pickup-time selection, queue token and estimated wait.
- Order tracking and in-app notifications for order lifecycle updates.
- Staff kitchen board to view orders, update statuses, adjust estimates, and verify collection.
- Admin dashboard for analytics, online sessions, staff activity, order history, and audit logs.
- Responsive pages for student, staff, and admin workflows.
- SQL schema and local SQLite database.
- Dockerfile and Docker Compose for containerized local run.
- Kubernetes namespace, deployment, service, secret/config map placeholders, ingress, and autoscaler manifests.
- GitHub Actions workflow to install dependencies, run tests, and build the Docker image.

## Run in VS Code on Windows

1. Extract the ZIP file.
2. In VS Code, choose **File → Open Folder** and select `smart-canteen`.
3. Open **Terminal → New Terminal** in that folder.
4. Run these commands one by one:

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python run.py
```

5. Open `http://127.0.0.1:5000` in your browser. Keep the terminal open while using the app.

You can also double-click `start.bat`. The first run needs internet access to install Flask, Werkzeug, and pytest. If installation fails, check your internet connection and try the commands again.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Student | `mugdha@example.com` | `Student@123` |
| Staff | `staff@example.com` | `Staff@123` |
| Admin | `admin@example.com` | `Admin@123` |

These accounts are for local demonstration only. Change or remove them before any public deployment.

## Run with Docker

Install and start Docker Desktop, then from the project folder run:

```bash
docker compose up --build
```

Open `http://127.0.0.1:5000`. Stop with `Ctrl+C`; use `docker compose down` to remove the container. The database directory is mounted so the local SQLite data persists between container runs.

## Git and GitHub

Install Git, then from the project folder:

```bash
git init
git add .
git commit -m "Initial Smart Canteen project"
git branch -M main
```

Create an empty repository on GitHub, then add its URL and push:

```bash
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main
```

The included `.github/workflows/ci.yml` automatically runs tests and builds the Docker image on pushes and pull requests to `main`/`master`. Do not commit `.env` files, passwords, or cloud credentials.

## Kubernetes

Kubernetes is optional for local development. Install Docker Desktop with Kubernetes enabled, or install a local cluster such as Minikube. Build the image first:

```bash
docker build -t smart-canteen:latest .
```

For a local cluster that can access the image, then run:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml
kubectl -n smart-canteen port-forward service/smart-canteen 8080:80
```

Open `http://127.0.0.1:8080`. Depending on your cluster, you may need to load the Docker image into the cluster or update the image reference in `k8s/deployment.yaml`. The secret file contains a placeholder only; replace it securely for a real deployment.

## AWS

See [`docs/AWS_DEPLOYMENT.md`](docs/AWS_DEPLOYMENT.md) for a deployment checklist for Amazon ECR + ECS Fargate or Amazon EKS. The guide does not create AWS resources automatically; you must configure your own account, IAM, network, secrets, and billing settings.

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

## Important deployment notes

- Local app uses SQLite, a SQL database suited to a single-instance college demo. **Do not scale this SQLite setup to multiple Kubernetes replicas** because each container can have its own database file. For production, migrate to Amazon RDS PostgreSQL/MySQL and a shared database adapter before horizontal scaling.
- `SECRET_KEY` defaults to a development value if not configured. Set a strong random value in your environment before deployment.
- The included `k8s/hpa.yaml` is a learning template and requires a metrics server and resource requests/limits to be configured for reliable autoscaling.
- The app is not a payment gateway; checkout records canteen orders but does not process real online payments.
