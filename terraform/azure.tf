provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
}

resource "azurerm_resource_group" "rg" {
  name     = "codeguard-rg"
  location = "eastus"
}

resource "azurerm_container_app_environment" "env" {
  name                = "codeguard-env"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_container_app" "codeguard" {
  name                         = "codeguard"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"

  secret {
    name  = "gemini-api-key"
    value = var.gemini_api_key
  }
  secret {
    name  = "api-key"
    value = var.api_key
  }

  template {
    min_replicas = 0 # scale to zero = free when idle
    max_replicas = 1
    container {
      name   = "codeguard"
      image  = "ghcr.io/${var.image_path}"
      cpu    = 1.0
      memory = "2Gi"
      env {
        name        = "GEMINI_API_KEY"
        secret_name = "gemini-api-key"
      }
      env {
        name        = "API_KEY"
        secret_name = "api-key"
      }
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

output "azure_url" { value = "https://${azurerm_container_app.codeguard.ingress[0].fqdn}" }
