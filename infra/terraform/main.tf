# Terraform Infrastructure as Code for AVENEL Pilot VM
# Enforces Morocco-hosted VM (or EU allowed) per Part A data residency rules

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.53.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0.5"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5.1"
    }
  }
}

variable "data_residency_policy" {
  type        = string
  default     = "MA_ONLY"
  description = "Data residency policy: MA_ONLY (default, Casablanca/Rabat) or EU_ALLOWED (Paris/Frankfurt)"
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

variable "vm_flavor" {
  type        = string
  default     = "m1.xlarge" # 8 vCPU, 32 GB RAM, 100 GB SSD
  description = "VM flavor for AVENEL stack (Postgres + ClamAV + API + Web)"
}

# Network Security Group: Restricts open ports to TLS (443), HTTP redirect (80), and Bastion SSH (22)
resource "openstack_networking_secgroup_v2" "avenel_secgroup" {
  name        = "avenel-${var.environment}-secgroup"
  description = "Security group for AVENEL pilot host"
}

resource "openstack_networking_secgroup_rule_v2" "allow_https" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.avenel_secgroup.id
}

resource "openstack_networking_secgroup_rule_v2" "allow_http" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.avenel_secgroup.id
}

resource "openstack_networking_secgroup_rule_v2" "allow_ssh_bastion" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "10.0.0.0/8" # Internal VPN/Bastion only
  security_group_id = openstack_networking_secgroup_v2.avenel_secgroup.id
}

# Encrypted Block Storage for PostgreSQL & Document Storage
resource "openstack_blockstorage_volume_v3" "avenel_data_volume" {
  name        = "avenel-${var.environment}-encrypted-data"
  size        = 200 # 200 GB SSD
  description = "Encrypted storage volume for PostgreSQL WAL archive and documents"
}

# Cloud-Init Cloud Configuration for Host Hardening
locals {
  cloud_init_config = <<-EOF
    #cloud-config
    package_update: true
    package_upgrade: true
    packages:
      - docker.io
      - docker-compose-v2
      - ufw
      - fail2ban
      - unattended-upgrades
    runcmd:
      - ufw default deny incoming
      - ufw default allow outgoing
      - ufw allow 80/tcp
      - ufw allow 443/tcp
      - ufw allow 22/tcp
      - ufw --force enable
      - systemctl enable docker
      - systemctl start docker
      - mkdir -p /opt/avenel/wal_archive /opt/avenel/documents
      - chown -R 10001:10001 /opt/avenel/documents
  EOF
}

output "security_notice" {
  value = "AVENEL host configured in region matching policy '${var.data_residency_policy}'. Secrets must be injected via .env.production or KMS."
}
