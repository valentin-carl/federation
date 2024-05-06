terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "5.27.0"
    }
  }
}

provider "google" {
  credentials = file("credentials.json")

  project = "workflows-413409"
  region = "europe-west10"
  zone = "europe-west10-a"
}

module "startup-scripts" {
  source  = "terraform-google-modules/startup-scripts/google"
  version = "2.0.0"
}

resource "google_compute_instance_template" "tinyfaas-template" {
  name = "tinyfaas-template"
  machine_type = "e2-medium"

  disk {
    source_image = "ubuntu-2204-jammy-v20240501"
    auto_delete = true
    disk_size_gb = 25
    boot = true
  }

  network_interface {
    network = "default"
    access_config {}
  }
}

resource "google_compute_instance_from_template" "tinyfaas" {
  name = "tinyfaas"
  zone = "europe-west10-a"

  source_instance_template = google_compute_instance_template.tinyfaas-template.self_link

  metadata_startup_script = file("startup.sh")

  network_interface {
    network = "default"
    access_config {}
  }

  tags = ["http-server", "https-server", "tinyfaas"]
}

resource "google_compute_firewall" "default" {
  name    = "firewall"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8000", "8080", "8081"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags = ["tinyfaas"]
}
