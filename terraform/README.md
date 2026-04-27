# Emet AWS infrastructure (Terraform)

Creates:

| Resource | Purpose |
|----------|---------|
| **SQS queue** + **DLQ** | Backend `SQS_QUEUE_URL` — async fact-check jobs (`worker_sqs.py` or Lambda). Workers must receive the **same** root `.env` as the API (including **`EMET_MCP_*`**, **`LLM_BASE_URL`**, **`OPENAI_API_KEY`**) so MCP and LLM routing match the web tier. |
| **S3 bucket** + **CloudFront** | Static frontend hosting — output **`cloudfront_url`** maps to `CLOUDFRONT_URL` and `CORS_ORIGINS`. |

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) `>= 1.5`
- AWS credentials (`aws configure` or env vars) with permission to create SQS, S3, CloudFront, IAM policy on bucket

## Apply

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # edit if needed
terraform init
terraform plan
terraform apply
```

Copy outputs:

```bash
terraform output -raw sqs_queue_url
terraform output -raw cloudfront_url
```

### Repo root `.env` (same file the API and worker use)

```bash
SQS_QUEUE_URL=<sqs_queue_url output>
AWS_REGION=us-east-1   # must match var.aws_region
CLOUDFRONT_URL=<cloudfront_url output>

# Allow browser calls from deployed UI + local dev:
CORS_ORIGINS=http://localhost:3000,<cloudfront_url output>
```

### Frontend (deployed build)

Point `NEXT_PUBLIC_API_URL` at your **API** (API Gateway, ALB, etc.—not created here).  
Set optional branding:

```bash
CLOUDFRONT_URL=https://dxxxx.cloudfront.net   # documentation / redirects only unless app reads it
```

## Static export → S3

This stack assumes you upload **static files** (`index.html`, assets). For Next.js:

1. Enable static export in `next.config` (`output: 'export'`) **if** your app can run without SSR for all routes you need (Clerk works with client-only patterns; validate sign-in flows).
2. Build and sync:

```bash
cd ../frontend
npm run build
# if using output export, dist is often `out/`
aws s3 sync out/ s3://$(cd ../terraform && terraform output -raw s3_bucket_name)/ --delete
aws cloudfront create-invalidation --distribution-id $(cd ../terraform && terraform output -raw cloudfront_distribution_id) --paths "/*"
```

If you keep hosting the UI on **Vercel**, you can still **`terraform apply` only the SQS** resources by moving S3/CloudFront to a separate module later—or delete the CloudFront resources from this config and keep SQS only.

## IAM (worker / API)

Grant the process that calls `send_message` (API) and `receive_message` (worker):

- `sqs:SendMessage` on `sqs_queue_arn`
- `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` on the same queue

Attach via IAM role (EC2, ECS, Lambda) or user policy for development.

## Destroy

```bash
terraform destroy
```

Empty the S3 bucket first if `terraform destroy` fails on non-empty bucket.
