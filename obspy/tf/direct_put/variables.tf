variable "snowflake_account" {
  description = "Snowflake Account Name."
  type        = string
}

variable "snowflake_organization_name" {
  description = "Snowflake Organization Name."
  type        = string
}

variable "snowflake_admin_user" {
  description = "Snowflake Admin User."
  type        = string
}

variable "snowflake_admin_role" {
  description = "Snowflake Admin Role."
  type        = string
}

variable "snowflake_admin_private_key_path" {
  description = "Path to the private key for the Snowflake admin user"
  type        = string
}

variable "firehose_user_private_key_path" {
  description = "Path to the private key for the Snowflake Firehose user"
  type        = string
}

variable "firehose_user_public_key_path" {
  description = "Path to the public key for the Snowflake Firehose user"
  type        = string
}

variable "snowflake_firehose_user" {
  description = "Snowflake user for authentication"
  type        = string
}

variable "snowflake_firehose_role" {
  description = "Snowflake Role."
  type        = string
}

variable "snowflake_firehose_warehouse" {
  description = "Warehouse for the Snowflake user."
  type        = string
}

variable "database_name" {
  description = "Snowflake database name."
  type        = string
}

variable "schema_name" {
  description = "Snowflake schema name."
  type        = string
}

variable "table_name" {
  description = "Name of the pipe."
  type        = string
}

variable "auto_ingest" {
  description = "Enable auto-ingest for the pipe."
  type        = bool
  default     = true
}

variable "custom_ingest_columns" {
  description = "Key value map, 'source_columns' and 'target_columns', containing comma separated table columns."
  type        = map(list(string))
  default = {
    source_columns = [],
    target_columns = [],
  }
}

variable "file_format" {
  description = "Source file format and options."
  type        = string
  default     = "TYPE = JSON NULL_IF = []"
}
