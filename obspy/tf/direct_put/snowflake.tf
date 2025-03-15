terraform {
  required_providers {
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 1.0.0" # Version is important to avoid authentication errors
    }
  }
}

# Configuration of the provider with private key authentication.
provider "snowflake" {
  account_name             = var.snowflake_account
  organization_name        = var.snowflake_organization_name
  private_key              = file(var.snowflake_admin_private_key_path)
  role                     = var.snowflake_admin_role
  user                     = var.snowflake_admin_user
  authenticator            = "SNOWFLAKE_JWT"
  preview_features_enabled = ["snowflake_table_resource"] # Enable preview feature
}

# Register the Firehose account role
resource "snowflake_account_role" "snowflake_firehose_account_role" {
  name    = var.snowflake_firehose_role
  comment = "Role for AWS Firehose to insert data into Snowflake"
}

# Register the Firehose user
resource "snowflake_user" "firehose_user" {
  name              = var.snowflake_firehose_user
  comment           = "User for AWS Firehose to insert data into Snowflake"
  default_role      = snowflake_account_role.snowflake_firehose_account_role.name
  default_warehouse = var.snowflake_firehose_warehouse
  rsa_public_key    = file(var.firehose_user_public_key_path)
}

# Assign FIREHOSE_ROLE to FIREHOSE_USER
resource "snowflake_grant_account_role" "assign_firehose_role_to_user" {
  role_name = snowflake_account_role.snowflake_firehose_account_role.name
  user_name = snowflake_user.firehose_user.name
}

# Assign FIREHOSE_ROLE to ACCOUNTADMIN (Optional, for visibility)
resource "snowflake_grant_account_role" "assign_firehose_role_to_admin" {
  role_name        = snowflake_account_role.snowflake_firehose_account_role.name
  parent_role_name = "ACCOUNTADMIN"
}

# Snowflake database
resource "snowflake_database" "db" {
  name    = var.database_name
  comment = "Terraform-managed Snowflake database"
}

# Snowflake schema
resource "snowflake_schema" "schema" {
  database = snowflake_database.db.name
  name     = var.schema_name
  comment  = "Terraform-managed Snowflake schema"
}

# Snowflake table
resource "snowflake_table" "table" {
  database = snowflake_database.db.name
  schema   = snowflake_schema.schema.name
  name     = var.table_name

  column {
    name = "id"
    type = "NUMBER"
  }

  column {
    name = "time"
    type = "TIMESTAMP_NTZ(6)"
  }

  column {
    name = "latitude"
    type = "FLOAT"
  }

  column {
    name = "longitude"
    type = "FLOAT"
  }

  column {
    name = "magnitude"
    type = "FLOAT"
  }
}

# Create a Stream on Table
resource "snowflake_stream_on_table" "stream" {
  name     = "${snowflake_table.table.name}-firehose-stream"
  schema   = snowflake_schema.schema.name
  database = snowflake_database.db.name

  table = snowflake_table.table.fully_qualified_name
}

# Grant OWNERSHIP of the database to FIREHOSE_ROLE (which removes all previous grants)
#resource "snowflake_grant_ownership" "firehose_database_ownership" {
#  account_role_name = snowflake_account_role.snowflake_firehose_account_role.name
#  on {
#    object_type = "DATABASE"
#    object_name = snowflake_database.db.name
#  }

#  depends_on = [
#    snowflake_database.db,   # Ensure the database exists
#    snowflake_schema.schema, # Ensure the schema is created
#    snowflake_table.table    # Ensure the table exists before transferring ownership
#  ]
#}

# Grant USAGE and CREATE SCHEMA on the database to FIREHOSE_ROLE
resource "snowflake_grant_privileges_to_account_role" "firehose_database_privileges" {
  account_role_name = snowflake_account_role.snowflake_firehose_account_role.name
  privileges        = ["USAGE", "CREATE SCHEMA"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.db.name
  }
}

# Grant OWNERSHIP of the schema to FIREHOSE_ROLE (which removes all previous grants)
#resource "snowflake_grant_ownership" "firehose_schema_ownership" {
#  account_role_name = snowflake_account_role.snowflake_firehose_account_role.name
#  on {
#    object_type = "SCHEMA"
#    object_name = "${snowflake_database.db.name}.${snowflake_schema.schema.name}"
#  }
#  depends_on = [
#    snowflake_schema.schema, # Prevent transfer before schema creation
#    snowflake_table.table    # Ensure schema owns the table first
#  ]
#}

# Grant privileges to the Firehose account role on the schema
resource "snowflake_grant_privileges_to_account_role" "firehose_schema_privileges" {
  account_role_name = snowflake_account_role.snowflake_firehose_account_role.name
  privileges        = ["USAGE", "CREATE TABLE"]
  on_schema {
    schema_name = "${snowflake_database.db.name}.${snowflake_schema.schema.name}"
  }
}

# Grant privilege on the table to the Firehose role
resource "snowflake_grant_privileges_to_account_role" "firehose_table_privileges" {
  privileges        = ["SELECT", "INSERT"]
  account_role_name = snowflake_account_role.snowflake_firehose_account_role.name
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = "${snowflake_database.db.name}.${snowflake_schema.schema.name}"
    }
  }
  depends_on = [snowflake_table.table]
}


#Register the Firehose database role
#resource "snowflake_database_role" "snowflake_firehose_database_role" {
#  database = snowflake_database.db.name
#  name     = "snowflake_firehose_database_role"
#}

# Grant the Firehose account role to the Firehose database role
#resource "snowflake_grant_database_role" "g" {
#  # database_role_name = "\"${var.database}\".\"${snowflake_database_role.database_role.name}\""
#  database_role_name = "earthsounds.snowflake_firehose_database_role"
#  parent_role_name   = snowflake_account_role.snowflake_firehose_account_role.name
#}


# This stage is used by the Snowpipe to load data from S3
# resource "snowflake_pipe" "firehose_pipe" {
#   database    = var.database_name
#   schema      = var.schema_name
#   name        = "FIREHOSE_PIPE"
#   auto_ingest = true # Enables HTTP-based ingestion
# }

# To use the streaming API, create the pipe
# (requires snowflake-connector-python / snowflake-snowsql?)
# resource "null_resource" "create_firehose_pipe" {
#  provisioner "local-exec" {
#    command = <<EOT
#      snowsql -a ${var.snowflake_organization_name}-${var.snowflake_account} \
#      -u ${var.snowflake_user} \
#      --private-key-path ${var.snowflake_private_key_path} \
#      -o exit_on_error=true -q "
#      CREATE OR REPLACE PIPE ${var.database_name}.${var.schema_name}.FIREHOSE_PIPE 
#      AUTO_INGEST = TRUE;"
#    EOT
#  }
#}
