terraform {
  required_providers {
    google  = { source = "hashicorp/google", version = "~> 6.0" }
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}

variable "gcp_project" {
  description = "Google Cloud project ID"
}

variable "azure_subscription_id" {
  description = "Azure subscription ID"
}

variable "image_path" {
  description = "Image on ghcr.io without the registry, e.g. yourname/codeguard-ai:latest"
}

variable "gemini_api_key" {
  sensitive = true
}

variable "api_key" {
  description = "Key users must send in the X-API-Key header"
  sensitive   = true
}

variable "llm_model" {
  default = "gemini-2.5-flash"
}
