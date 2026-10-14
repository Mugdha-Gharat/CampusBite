# AWS deployment guide

This project is packaged for local development with Flask + SQLite. Use the Docker image as a learning/demo deployment. **Do not run multiple replicas with the bundled SQLite database in production**: SQLite is stored in a local file and is not a shared database. For a production deployment, first migrate the database layer/schema to Amazon RDS for PostgreSQL or MySQL and configure durable shared storage/secrets.

## Option A — Amazon ECS with ECR (simplest container path)

1. Create an AWS ECR repository named `smart-canteen` in your selected AWS region.
2. Install and configure AWS CLI credentials locally (`aws configure`), then authenticate Docker to ECR using the command shown by the ECR console (`aws ecr get-login-password ... | docker login ...`).
3. Build the image from this folder: `docker build -t smart-canteen .`
4. Tag and push the image using your ECR repository URI: `docker tag smart-canteen:latest <ECR_URI>:latest` and `docker push <ECR_URI>:latest`.
5. Create an ECS Fargate task definition with container port `5000`, a health check against `/health`, and an environment variable `SECRET_KEY` sourced from AWS Secrets Manager or Systems Manager Parameter Store. Do not commit real secrets to Git.
6. Create an ECS service behind an Application Load Balancer. Configure HTTPS with AWS Certificate Manager and allow inbound traffic only through the load balancer.
7. Review CloudWatch logs and test `/health`, registration, ordering, and staff status changes.

The above is a deployment checklist, not an automatic AWS provisioner. AWS account, IAM, networking, database migration, and billing settings must be configured in your own account.

## Option B — Kubernetes / Amazon EKS

1. Build and push the image to ECR as described above.
2. Update `k8s/deployment.yaml` to use `<ECR_URI>:<tag>`.
3. Create an EKS cluster and configure `kubectl` for that cluster.
4. Create a namespace and secret using your deployment secret manager. The checked-in `k8s/secret.yaml` contains only a placeholder; never use it as a real production secret.
5. Apply manifests in this order: namespace, ConfigMap/Secret, Deployment, Service, then HPA. Configure an Ingress controller and TLS certificate before exposing the app publicly.
6. Configure RDS (PostgreSQL/MySQL) and update the app's database adapter before increasing replicas. The included app currently uses SQLite and is suitable for a local/demo deployment, not horizontally scaled production traffic.

## AWS safety checklist

- Use IAM least privilege and never commit AWS access keys.
- Store `SECRET_KEY` and database credentials in Secrets Manager/Parameter Store.
- Enable HTTPS, backups, log retention, alarms, and database encryption.
- Change all demo passwords and remove demo-account creation before a public deployment.
- Test authorization and recovery procedures before handling real student information.
