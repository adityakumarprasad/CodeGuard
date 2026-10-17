provider "google" {
  project = var.gcp_project
  region  = "us-central1"
}

resource "google_project_service" "run" { service = "run.googleapis.com" }
resource "google_project_service" "ar" { service = "artifactregistry.googleapis.com" }

# Cloud Run can't pull from ghcr.io directly, so Artifact Registry proxies it
resource "google_artifact_registry_repository" "ghcr" {
  location      = "us-central1"
  repository_id = "ghcr-proxy"
  format        = "DOCKER"
  mode          = "REMOTE_REPOSITORY"
  remote_repository_config {
    docker_repository {
      custom_repository { uri = "https://ghcr.io" }
    }
  }
  depends_on = [google_project_service.ar]
}

resource "google_cloud_run_v2_service" "codeguard" {
  name                = "codeguard"
  location            = "us-central1"
  deletion_protection = false

  template {
    timeout = "900s"                   # scans with fixes take time on the free tier
    scaling { max_instance_count = 1 } # cost cap, and our in-memory rate limit assumes one instance

    containers {
      image = "us-central1-docker.pkg.dev/${var.gcp_project}/ghcr-proxy/${var.image_path}"
      ports { container_port = 8080 }
      resources { limits = { memory = "1Gi", cpu = "1" } }
      env {
        name  = "GEMINI_API_KEY"
        value = var.gemini_api_key # for production, use Secret Manager
      }
      env {
        name  = "API_KEY"
        value = var.api_key
      }
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
    }
  }
  depends_on = [google_project_service.run, google_artifact_registry_repository.ghcr]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.codeguard.name
  location = google_cloud_run_v2_service.codeguard.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "gcp_url" { value = google_cloud_run_v2_service.codeguard.uri }
