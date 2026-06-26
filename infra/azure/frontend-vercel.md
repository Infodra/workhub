# Frontend Deployment (Vercel)

## 1. Import Project
- Import the repository in Vercel.
- Root directory: `frontend`.

## 2. Build Settings
- Build command: `npm run build`
- Output: `.next`

## 3. Environment Variables
Add all values from `frontend/.env.example`.

## 4. Redirect URI
Set `NEXT_PUBLIC_AZURE_REDIRECT_URI` to your Vercel domain.

## 5. CORS
Add frontend domain to `ALLOWED_ORIGINS` on backend.
