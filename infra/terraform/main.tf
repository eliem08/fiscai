# Terraform Infrastructure as Code for AVENEL Pilot Deployment
# Provider-Neutral Cloud-Init and VM Bootstrap for Moroccan Sovereign Datacenters (N+ONE, Inwi) and EU Fallback

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudinit = {
      source  = "hashicorp/cloudinit"
      version = "~> 2.3.5"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5.1"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0.6"
    }
  }
}

variable "data_residency_policy" {
  type        = string
  default     = "MA_ONLY"
  description = "Data residency policy: MA_ONLY (Morocco domestic - N+ONE / Inwi) or EU_ALLOWED (EU Sovereign - Scaleway / OVHcloud)"
  validation {
    condition     = contains(["MA_ONLY", "EU_ALLOWED"], var.data_residency_policy)
    error_message = "data_residency_policy must be either 'MA_ONLY' or 'EU_ALLOWED'."
  }
}

variable "environment" {
  type        = string
  default     = "pilot"
  description = "Environment identifier (pilot, production)"
}

variable "admin_ssh_allowed_cidr" {
  type        = string
  default     = "10.0.0.0/8"
  description = "CIDR block permitted to access SSH port 22 (VPN or Bastion host only)"
}

# 1. Generate SSH Key Pair for Host Administration (TLS Provider)
resource "tls_private_key" "host_ssh_key" {
  algorithm = "ED25519"
}

# 2. Cloud-Init Multipart Configuration (Provider-Neutral Bootstrap)
data "cloudinit_config" "avenel_bootstrap" {
  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"
    content      = <<-EOF
      #cloud-config
      package_update: true
      package_upgrade: true
      packages:
        - docker.io
        - docker-compose-v2
        - ufw
        - fail2ban
        - unattended-upgrades
        - curl
        - postgresql-client-16

      users:
        - name: avenel
          gecos: AVENEL Runtime Service User
          primary_group: docker
          groups: [docker]
          sudo: ALL=(ALL) NOPASSWD:ALL
          shell: /bin/bash
          ssh_authorized_keys:
            - ${tls_private_key.host_ssh_key.public_key_openssh}

      write_files:
        - path: /etc/systemd/system/avenel-stack.service
          permissions: '0644'
          content: |
            [Unit]
            Description=AVENEL Production Docker Compose Stack
            Requires=docker.service
            After=docker.service

            [Service]
            Type=oneshot
            RemainAfterExit=yes
            WorkingDirectory=/opt/avenel
            ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
            ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
            TimeoutStartSec=0

            [Install]
            WantedBy=multi-user.target

      runcmd:
        # Firewall & Network Hardening
        - ufw default deny incoming
        - ufw default allow outgoing
        - ufw allow 80/tcp comment 'HTTP ACME Challenge'
        - ufw allow 443/tcp comment 'HTTPS Production API & Web'
        - ufw allow from ${var.admin_ssh_allowed_cidr} to any port 22 proto tcp comment 'Bastion SSH'
        - ufw --force enable

        # Secure System Directories & Permissions
        - mkdir -p /opt/avenel/wal_archive /opt/avenel/documents /opt/avenel/backups
        - chown -R 10001:10001 /opt/avenel/documents /opt/avenel/wal_archive
        - chmod 700 /opt/avenel/wal_archive /opt/avenel/backups

        # Docker & Service Initialization
        - systemctl daemon-reload
        - systemctl enable docker fail2ban
        - systemctl start docker fail2ban
    EOF
  }
}

# 3. Save rendered user-data for deployment into VM management portals
resource "local_file" "rendered_cloud_init" {
  filename = "${path.module}/build/user-data.yaml"
  content  = data.cloudinit_config.avenel_bootstrap.rendered
}

resource "local_file" "private_key_pem" {
  filename        = "${path.module}/build/avenel_admin_ed25519"
  content         = tls_private_key.host_ssh_key.private_key_openssh
  file_permission = "0600"
}

output "cloud_init_user_data_path" {
  description = "Path to the rendered cloud-init file for VM provisioning"
  value       = local_file.rendered_cloud_init.filename
}

output "data_residency_target" {
  description = "Validated hosting residency target"
  value       = var.data_residency_policy == "MA_ONLY" ? "Morocco Sovereign Cloud (N+ONE Casablanca / Inwi)" : "EU Sovereign Cloud"
}
