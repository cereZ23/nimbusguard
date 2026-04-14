#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# LocalStack Seed — provisions deliberately INSECURE AWS resources
# so NimbusGuard can scan and produce real findings.
#
# Usage:
#   docker compose up localstack -d
#   bash infra/localstack-seed.sh
#
# Requires: awscli v2 (or awscli-local)
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

ENDPOINT="http://localhost:4566"
REGION="us-east-1"
ACCOUNT_ID="000000000000"

aws="aws --endpoint-url=$ENDPOINT --region=$REGION --no-cli-pager"

echo "=== NimbusGuard LocalStack Seed ==="
echo "Endpoint: $ENDPOINT"
echo ""

# ── S3 Buckets ────────────────────────────────────────────────────
echo "[S3] Creating buckets..."

# Bucket 1: INSECURE — no encryption, no versioning, no logging, public access
$aws s3api create-bucket --bucket insecure-data-bucket 2>/dev/null || true
$aws s3api delete-public-access-block --bucket insecure-data-bucket 2>/dev/null || true

# Bucket 2: SECURE — encryption, versioning, logging, public access blocked
$aws s3api create-bucket --bucket secure-logs-bucket 2>/dev/null || true
$aws s3api put-public-access-block --bucket secure-logs-bucket \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" 2>/dev/null || true
$aws s3api put-bucket-encryption --bucket secure-logs-bucket \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' 2>/dev/null || true
$aws s3api put-bucket-versioning --bucket secure-logs-bucket \
  --versioning-configuration Status=Enabled 2>/dev/null || true
$aws s3api put-bucket-logging --bucket secure-logs-bucket \
  --bucket-logging-status '{"LoggingEnabled":{"TargetBucket":"secure-logs-bucket","TargetPrefix":"logs/"}}' 2>/dev/null || true

# Bucket 3: PARTIAL — encryption but no versioning
$aws s3api create-bucket --bucket partial-config-bucket 2>/dev/null || true
$aws s3api put-bucket-encryption --bucket partial-config-bucket \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' 2>/dev/null || true

# Bucket 4: INSECURE — backup bucket, no encryption
$aws s3api create-bucket --bucket old-backup-bucket 2>/dev/null || true

echo "[S3] 4 buckets created (2 insecure, 1 partial, 1 secure)"

# ── EC2 Instances ─────────────────────────────────────────────────
echo "[EC2] Creating instances and security groups..."

# Create a VPC
VPC_ID=$($aws ec2 create-vpc --cidr-block 10.0.0.0/16 --query 'Vpc.VpcId' --output text 2>/dev/null || echo "vpc-12345")
$aws ec2 create-tags --resources "$VPC_ID" --tags Key=Name,Value=production-vpc 2>/dev/null || true

# Create subnet
SUBNET_ID=$($aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.0.1.0/24 --query 'Subnet.SubnetId' --output text 2>/dev/null || echo "subnet-12345")

# Security Group 1: INSECURE — SSH open to the world
SG_OPEN=$($aws ec2 create-security-group \
  --group-name open-ssh-sg \
  --description "INSECURE: SSH open to 0.0.0.0/0" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' --output text 2>/dev/null || echo "sg-open")
$aws ec2 authorize-security-group-ingress \
  --group-id "$SG_OPEN" \
  --protocol tcp --port 22 \
  --cidr 0.0.0.0/0 2>/dev/null || true

# Security Group 2: INSECURE — RDP open to the world
SG_RDP=$($aws ec2 create-security-group \
  --group-name open-rdp-sg \
  --description "INSECURE: RDP open to 0.0.0.0/0" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' --output text 2>/dev/null || echo "sg-rdp")
$aws ec2 authorize-security-group-ingress \
  --group-id "$SG_RDP" \
  --protocol tcp --port 3389 \
  --cidr 0.0.0.0/0 2>/dev/null || true

# Security Group 3: SECURE — restricted access
SG_SECURE=$($aws ec2 create-security-group \
  --group-name restricted-sg \
  --description "Restricted: only internal CIDR" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' --output text 2>/dev/null || echo "sg-secure")
$aws ec2 authorize-security-group-ingress \
  --group-id "$SG_SECURE" \
  --protocol tcp --port 443 \
  --cidr 10.0.0.0/16 2>/dev/null || true

# EC2 Instance 1: INSECURE — public IP, IMDSv1
INSTANCE_1=$($aws ec2 run-instances \
  --image-id ami-12345678 \
  --instance-type t3.micro \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_OPEN" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=web-server-public}]" \
  --query 'Instances[0].InstanceId' --output text 2>/dev/null || echo "i-public")

# EC2 Instance 2: SECURE — no public IP, IMDSv2 required
INSTANCE_2=$($aws ec2 run-instances \
  --image-id ami-12345678 \
  --instance-type t3.micro \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_SECURE" \
  --metadata-options "HttpTokens=required,HttpEndpoint=enabled" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=api-server-private}]" \
  --query 'Instances[0].InstanceId' --output text 2>/dev/null || echo "i-private")

# EBS Volume: INSECURE — unencrypted
$aws ec2 create-volume \
  --availability-zone us-east-1a \
  --size 100 \
  --volume-type gp3 \
  --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=unencrypted-data-vol}]" 2>/dev/null || true

# EBS Volume: SECURE — encrypted
$aws ec2 create-volume \
  --availability-zone us-east-1a \
  --size 50 \
  --volume-type gp3 \
  --encrypted \
  --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=encrypted-backup-vol}]" 2>/dev/null || true

echo "[EC2] VPC, 3 security groups, 2 instances, 2 volumes created"

# ── IAM ───────────────────────────────────────────────────────────
echo "[IAM] Creating users and policies..."

# User 1: INSECURE — console access, no MFA, old access key
$aws iam create-user --user-name admin-legacy 2>/dev/null || true
$aws iam create-login-profile --user-name admin-legacy --password "OldP@ss123!" --no-password-reset-required 2>/dev/null || true
$aws iam create-access-key --user-name admin-legacy 2>/dev/null || true
$aws iam attach-user-policy --user-name admin-legacy \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess 2>/dev/null || true

# User 2: INSECURE — console access, no MFA
$aws iam create-user --user-name dev-user 2>/dev/null || true
$aws iam create-login-profile --user-name dev-user --password "DevP@ss456!" --no-password-reset-required 2>/dev/null || true

# User 3: SECURE — programmatic only (no console), tagged
$aws iam create-user --user-name ci-bot --tags Key=team,Value=devops 2>/dev/null || true
$aws iam create-access-key --user-name ci-bot 2>/dev/null || true

echo "[IAM] 3 users created (2 with console access, no MFA)"

# ── RDS ───────────────────────────────────────────────────────────
echo "[RDS] Creating database instances..."

# RDS 1: INSECURE — publicly accessible, no encryption, low backup retention
$aws rds create-db-instance \
  --db-instance-identifier insecure-mysql-db \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --master-username admin \
  --master-user-password "InsecureP@ss1" \
  --allocated-storage 20 \
  --publicly-accessible \
  --backup-retention-period 1 \
  --no-storage-encrypted 2>/dev/null || true

# RDS 2: SECURE — private, encrypted, adequate backup
$aws rds create-db-instance \
  --db-instance-identifier secure-postgres-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password "SecureP@ss2!" \
  --allocated-storage 50 \
  --no-publicly-accessible \
  --backup-retention-period 14 \
  --storage-encrypted 2>/dev/null || true

echo "[RDS] 2 DB instances created (1 insecure, 1 secure)"

# ── Lambda ────────────────────────────────────────────────────────
echo "[Lambda] Creating functions..."

# Create a dummy Lambda zip
LAMBDA_DIR=$(mktemp -d)
echo 'def handler(event, context): return {"statusCode": 200}' > "$LAMBDA_DIR/index.py"
(cd "$LAMBDA_DIR" && zip -q function.zip index.py)

# Lambda 1: INSECURE — public resource policy
$aws lambda create-function \
  --function-name public-api-handler \
  --runtime python3.12 \
  --handler index.handler \
  --role "arn:aws:iam::${ACCOUNT_ID}:role/lambda-role" \
  --zip-file "fileb://$LAMBDA_DIR/function.zip" 2>/dev/null || true
$aws lambda add-permission \
  --function-name public-api-handler \
  --statement-id public-invoke \
  --action lambda:InvokeFunction \
  --principal "*" 2>/dev/null || true

# Lambda 2: SECURE — restricted policy
$aws lambda create-function \
  --function-name internal-processor \
  --runtime python3.12 \
  --handler index.handler \
  --role "arn:aws:iam::${ACCOUNT_ID}:role/lambda-role" \
  --zip-file "fileb://$LAMBDA_DIR/function.zip" 2>/dev/null || true

rm -rf "$LAMBDA_DIR"
echo "[Lambda] 2 functions created (1 with public access)"

# ── CloudTrail ────────────────────────────────────────────────────
echo "[CloudTrail] Creating trail..."

$aws s3api create-bucket --bucket cloudtrail-logs-bucket 2>/dev/null || true
$aws cloudtrail create-trail \
  --name main-trail \
  --s3-bucket-name cloudtrail-logs-bucket \
  --is-multi-region-trail 2>/dev/null || true
$aws cloudtrail start-logging --name main-trail 2>/dev/null || true

echo "[CloudTrail] 1 multi-region trail created"

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo "=== Seed Complete ==="
echo ""
echo "Resources created:"
echo "  S3 Buckets:        4 (2 insecure, 1 partial, 1 secure)"
echo "  EC2 Instances:     2 (1 public+IMDSv1, 1 private+IMDSv2)"
echo "  Security Groups:   3 (SSH open, RDP open, restricted)"
echo "  EBS Volumes:       2 (1 unencrypted, 1 encrypted)"
echo "  IAM Users:         3 (2 with console, no MFA)"
echo "  RDS Instances:     2 (1 public+unencrypted, 1 private+encrypted)"
echo "  Lambda Functions:  2 (1 public, 1 restricted)"
echo "  CloudTrail:        1 multi-region trail"
echo "  VPC:               1 (no flow logs)"
echo ""
echo "Expected findings: ~15-20 (mix of pass/fail across 20 CIS-AWS checks)"
echo ""
echo "To scan with NimbusGuard:"
echo "  1. Register at http://localhost:3000"
echo "  2. Add AWS account with:"
echo "     - Access Key ID: test"
echo "     - Secret Access Key: test"
echo "     - Region: us-east-1"
echo "  3. Trigger a scan"
echo ""
echo "Backend must have AWS_ENDPOINT_URL=http://localhost:4566"
