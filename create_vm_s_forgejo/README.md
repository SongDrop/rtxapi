```
 ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄   ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄     ▄▄▄ ▄▄▄▄▄▄▄
█       █       █   ▄  █ █       █       █   █   █       █
█    ▄▄▄█   ▄   █  █ █ █ █   ▄▄▄▄█    ▄▄▄█   █   █   ▄   █
█   █▄▄▄█  █ █  █   █▄▄█▄█  █  ▄▄█   █▄▄▄ ▄  █   █  █ █  █
█    ▄▄▄█  █▄█  █    ▄▄  █  █ █  █    ▄▄▄█ █▄█   █  █▄█  █
█   █   █       █   █  █ █  █▄▄█ █   █▄▄▄█       █       █
█▄▄▄█   █▄▄▄▄▄▄▄█▄▄▄█  █▄█▄▄▄▄▄▄▄█▄▄▄▄▄▄▄█▄▄▄▄▄▄▄█▄▄▄▄▄▄▄█

```

# Forgejo Self-Hosted Git Client Server on Azure

This is an **automatic installation** on Azure to set up a forgejo self-hosted git server.

---

## Step 1: Create a Microsoft Azure account on https://portal.azure.com

## Step 2: Point your DNS records to Microsoft Azure

## Step 3: Create a new Application in Microsoft Entra ID and fill out the .evn

## Step 4: Run setup script for automatic software installation on the virtual machine

---

---

> **Important:**  
> You will need to update your domain's nameservers at your registrar (e.g., Namecheap) to the following Azure DNS nameservers:
>
> - ns1-01.azure-dns.com
> - ns2-01.azure-dns.net
> - ns3-01.azure-dns.org
> - ns4-01.azure-dns.info
>
> Make sure your DNS records point to Azure **before** you start the installation.

---

## Required `.env` values for Azure:

You need to provide the following values in your `.env` file:

```
Azure subscription -> portal.azure.com

AZURE_SUBSCRIPTION_ID=''  # https://portal.azure.com/#view/Microsoft_Azure_Billing/SubscriptionsBladeV2
AZURE_TENANT_ID=''        # https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/Overview
AZURE_APP_CLIENT_ID=''
AZURE_APP_CLIENT_SECRET=''
AZURE_APP_TENANT_ID=''
```

You also need to create a new Azure Application in Azure Entra ID (Azure Active Directory) to get these credentials.

---

## To start:

```bash
python3 -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt
python3 create_vm.py
```

---

## After that, just input these values when prompted, and your email service will be up and running within 5 minutes:

```
Enter VM username [azureuser]:
Enter VM password [azurepassword1234!]:
Enter main domain [example.com]:
Enter subdomain (e.g., 'forgejo') [forgejo]:
[INFO] Full domain to configure: forgejo.example.com
Enter resource group name [forgejogroup]:
Enter VM name [stmp]:
Enter Azure region [uksouth]:
Enter VM size [Standard_B2s]:
Enter admin email [admin@example.com]:
Enter admin password [forgejopass123!]:
Enter disk size in GB [1024]:
```

> You might also need to request Azure quota increase for the specific virtual machine size you plan to use.

---

Happy mailing with your new forgejo setup on Azure! 🚀
