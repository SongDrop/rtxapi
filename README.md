# rtxapi

api for rtx windows10

STEP-1: Create the virtual machine and the resources needed
STEP-2: Upload and run script for automatic software installation on virtual machine

python3 -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt
python3 create_vm.py

python3 -m venv myenv
source myenv/bin/activate
python3 create_vm_ue3.py

python3 -m venv myenv
source myenv/bin/activate
python3 delete_vm.py

# Azure Service Principal Setup and Permissions for Python Provisioning Script

This guide explains the steps to configure an Azure AD application (service principal) with the necessary permissions to run your Python Azure provisioning script.

---

## 1. You have Azure Subscription Admin Access

- You have admin or owner privileges on an Azure subscription identified by a **Subscription ID**.
- This subscription is the scope where your resources will be created (resource groups, VMs, networks, etc).

---

## 2. Create an Azure AD Application (Service Principal)

1. Go to **Azure Portal** > **Azure Active Directory** > **App registrations** > **New registration**.
2. Register a new application.
3. Note the following values:
   - **Application (client) ID** → `app_client_id`
   - **Directory (tenant) ID** → `app_tenant_id`

---

## 3. Create a Client Secret

1. In your app registration, navigate to **Certificates & secrets**.
2. Click **New client secret**.
3. Create a secret and save the **client secret value**.
   - **Application (client secret) ID** → `app_secret_id`

---

## 4. Assign Azure RBAC Roles to the Service Principal

1. Navigate to **Subscriptions** > select your subscription > **Access Control (IAM)** > **Role assignments**.
2. Click **+ Add** > **Add role assignment**.
3. Select the **Contributor** role (or other necessary roles).
4. In **Assign access to**, choose **User, group, or service principal**.
5. Search for your registered application by name or client ID.
6. Assign the role at the **subscription** or **resource group** scope as needed.
   Subscription or resource group scope is:
   Contributor
   If you want to follow least privilege and split roles, assign all these:
   Resource Group Contributor
   Storage Account Contributor
   Storage Blob Data Contributor
   Network Contributor
   Virtual Machine Contributor
   DNS Zone Contributor

---

## 5. Configure Environment Variables for Your Python Script

Set the following environment variables with the values from your Azure AD app and subscription:

```bash
AZURE_SUBSCRIPTION_ID=<your-subscription-id>
AZURE_TENANT_ID=<your-directory-tenant-id>
AZURE_APP_CLIENT_ID=<your-application-client-id>
AZURE_APP_CLIENT_SECRET=<your-application-client-secret>
AZURE_APP_TENANt_ID=<your-application-teant-id>
```
