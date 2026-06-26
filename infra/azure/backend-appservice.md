# Backend Deployment (Azure App Service)

## 1. Create Resources
- Create App Service Plan (Linux, B1+).
- Create Web App for Containers or Python runtime.
- Set startup command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

## 2. Configure Environment Variables
Configure all keys from `backend/.env.example` in App Service Configuration.

## 3. Identity and Secrets
- Store `CLIENT_SECRET` in Key Vault and reference it in App Service.
- Enable system-assigned managed identity for secret access.

## 4. Deploy
- Connect GitHub repository or use Azure DevOps pipeline.
- Deploy `backend/` directory.

## 5. Health Check
- Set health check path to `/health`.

## 6. Scale and Monitoring
- Enable autoscale by CPU.
- Enable Application Insights.
- Configure log retention.
