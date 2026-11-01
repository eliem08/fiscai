# AVENEL Infrastructure & Terraform Guide

## 1. Provider Sources & Official Registry Verification

In compliance with Phase 5b architectural guidelines, every Terraform provider is sourced strictly from official registries:

| Provider | Source Identifier | Registry URL | Purpose |
|---|---|---|---|
| **CloudInit** | `hashicorp/cloudinit` | `registry.terraform.io/hashicorp/cloudinit` | Generates multipart `#cloud-config` user-data for VM bootstrap |
| **Local** | `hashicorp/local` | `registry.terraform.io/hashicorp/local` | Writes out rendered user-data script and SSH administration keys |
| **TLS** | `hashicorp/tls` | `registry.terraform.io/hashicorp/tls` | Generates ED25519 cryptographic key pair for host administration |

### Note on Moroccan Datacenter Providers (N+ONE & Inwi Cloud)
Neither **N+ONE Datacenters** (Casablanca/Bouskoura/Settat) nor **Inwi Enterprise Cloud** publish official providers in the HashiCorp Terraform Registry:
- **Inwi Cloud:** Backed by an OpenStack / VMware enterprise infrastructure managed through a bespoke customer self-service portal or OpenStack APIs.
- **N+ONE Datacenters:** Utilizes VMware vCloud Director / Cloud Director portal or physical bare-metal co-location.

To avoid non-existent or fragile third-party provider dependencies, AVENEL utilizes a **provider-neutral VM bootstrap** architecture:
1. Terraform compiles a hardened `#cloud-config` (`infra/terraform/build/user-data.yaml`).
2. The user-data is pasted directly into the cloud provider's provisioning portal or VM creation API.
3. Upon first boot, the Linux kernel cloud-init agent executes network hardening, firewall isolation (UFW), creates unprivileged user `avenel` (UID 10001), and automatically brings up `docker-compose.prod.yml`.

---

## 2. Validation & Deployment Instructions

### Step 1: Initialize and Validate Terraform
```bash
cd infra/terraform
terraform init
terraform validate
```

### Step 2: Render Bootstrap Artifacts
```bash
terraform apply -auto-approve
```
This renders:
- `infra/terraform/build/user-data.yaml`
- `infra/terraform/build/avenel_admin_ed25519`

### Step 3: VM Provisioning on Moroccan Clouds
- **Inwi Enterprise Cloud:**
  1. Navigate to *Instances > Launch Instance*.
  2. Select Ubuntu 24.04 LTS / 22.04 LTS.
  3. Under *Configuration*, paste the contents of `build/user-data.yaml`.
  4. Associate public IP and start instance.
- **N+ONE VMware vCloud Director:**
  1. Deploy new vApp from Ubuntu template.
  2. Under *Guest OS Customization*, enable cloud-init and attach `user-data.yaml`.
  3. Power on VM.
