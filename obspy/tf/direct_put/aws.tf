resource "aws_iam_role" "firehose_role" {
  name = "firehose_to_snowflake_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "firehose.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

# IAM Policy for Firehose to Snowflake
resource "aws_iam_policy" "firehose_policy" {
  name        = "firehose_to_snowflake_policy"
  description = "Policy for Kinesis Firehose to write to Snowflake"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = "arn:aws:s3:::earthsounds-firehose/*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:PutLogEvents", "logs:CreateLogStream", "logs:DescribeLogStreams", "logs:DescribeLogGroups"]
        Resource = "arn:aws:logs:us-west-2:897729117324:log-group:/aws/kinesisfirehose/firehose-to-snowflake:*"
      },
      {
        "Effect" : "Allow",
        "Action" : "execute-api:Invoke",
        "Resource" : "arn:aws:execute-api:us-west-2:897729117324:zspvuzn-nob03514.snowflakecomputing.com/*"
      }
    ]
  })
}

# Attach the policy to the role
resource "aws_iam_role_policy_attachment" "attach_policy" {
  role       = aws_iam_role.firehose_role.name
  policy_arn = aws_iam_policy.firehose_policy.arn
}

# AWS S3 Bucket for Firehose Backup
resource "aws_s3_bucket" "firehose_backup" {
  bucket = "earthsounds-firehose"
}

resource "aws_kinesis_firehose_delivery_stream" "firehose_to_snowflake2" {
  # (resource arguments)
}

# AWS Kinesis Firehose Delivery Stream
resource "aws_kinesis_firehose_delivery_stream" "firehose_to_snowflake" {
  name        = "firehose-to-snowflake"
  destination = "http_endpoint"

  http_endpoint_configuration {
    url                = "https://nqb40464.us-west-2.privatelink.snowflakecomputing.com:443"
    name               = "Snowflake"
    access_key         = aws_iam_role.firehose_role.arn
    role_arn           = aws_iam_role.firehose_role.arn
    buffering_size     = 5
    buffering_interval = 60

    request_configuration {
      content_encoding = "GZIP"
    }

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose_logs.name
      log_stream_name = "firehose-to-snowflake-stream"
    }

    s3_configuration {
      role_arn            = aws_iam_role.firehose_role.arn
      bucket_arn          = aws_s3_bucket.firehose_backup.arn
      prefix              = "failed/"
      buffering_interval  = 60
      buffering_size      = 5
      compression_format  = "GZIP"
      error_output_prefix = "error/"
    }
  }
}

# Cloudwatch Log Group
resource "aws_cloudwatch_log_group" "firehose_logs" {
  name              = "/aws/kinesisfirehose/firehose-to-snowflake"
  retention_in_days = 7
}
