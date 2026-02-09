import pandas as pd
from simple_salesforce import Salesforce
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import random

load_dotenv()

sf = Salesforce(
    consumer_key=os.getenv("SF_CONSUMER_KEY"),
    consumer_secret=os.getenv("SF_CONSUMER_SECRET"),
    domain=os.getenv("SF_DOMAIN"),
)

print("=" * 60)
print("SALESFORCE DEMO DATA UPLOADER")
print("=" * 60)

# Step 1: Upload Products
print("\n[1/4] Uploading Products...")
products_df = pd.read_csv("Salesforce_GovCon_Demo_Pack/products.csv")
product_ids = {}

for idx, row in products_df.iterrows():
    try:
        result = sf.Product2.create(
            {
                "Name": row["Name"],
                "ProductCode": row["ProductCode"],
                "Family": row["Family"],
                "IsActive": bool(row["IsActive"]),
                "Description": row["Description"],
            }
        )
        product_ids[row["ProductCode"]] = result["id"]
        print(f"  ✓ {row['Name']}")
    except Exception as e:
        print(f"  ✗ {row['Name']}: {e}")

print(f"\n✓ Uploaded {len(product_ids)} products")

# Step 2: Create Sample Accounts
print("\n[2/4] Creating Sample Accounts...")
accounts = [
    {"Name": "Department of Defense", "Industry": "Government"},
    {"Name": "Department of Homeland Security", "Industry": "Government"},
    {"Name": "Federal Aviation Administration", "Industry": "Government"},
    {"Name": "National Security Agency", "Industry": "Government"},
    {"Name": "US Customs & Border Protection", "Industry": "Government"},
]
account_ids = []

for acc in accounts:
    try:
        result = sf.Account.create(acc)
        account_ids.append(result["id"])
        print(f"  ✓ {acc['Name']}")
    except Exception as e:
        print(f"  ✗ {acc['Name']}: {e}")

print(f"\n✓ Created {len(account_ids)} accounts")

# Step 3: Create Sample Contracts (for renewal pipeline)
print("\n[3/4] Creating Sample Contracts...")
contract_count = 0

for i, account_id in enumerate(account_ids):
    # Create 2-3 contracts per account
    for j in range(random.randint(2, 3)):
        start_date = datetime.now() - timedelta(days=random.randint(180, 540))
        contract_term = random.choice([12, 24, 36])
        end_date = start_date + timedelta(days=contract_term * 30)

        try:
            result = sf.Contract.create(
                {
                    "AccountId": account_id,
                    "Status": "Draft",
                    "StartDate": start_date.strftime("%Y-%m-%d"),
                    "ContractTerm": contract_term,
                }
            )
            contract_id = result["id"]

            # Activate contract
            sf.Contract.update(contract_id, {"Status": "Activated"})
            contract_count += 1
            print(
                f"  ✓ Contract {contract_count} (expires: {end_date.strftime('%Y-%m-%d')})"
            )
        except Exception as e:
            print(f"  ✗ Contract creation failed: {e}")

print(f"\n✓ Created {contract_count} contracts")

# Step 4: Create Sample Opportunities (for sales pipeline)
print("\n[4/4] Creating Sample Opportunities...")
stages = [
    "Prospecting",
    "Qualification",
    "Needs Analysis",
    "Value Proposition",
    "Proposal/Price Quote",
    "Negotiation/Review",
]
opp_count = 0

for i, account_id in enumerate(account_ids):
    # Create 3-5 opportunities per account
    for j in range(random.randint(3, 5)):
        product_code = random.choice(list(product_ids.keys()))
        product_name = products_df[products_df["ProductCode"] == product_code][
            "Name"
        ].iloc[0]
        amount = random.randint(50000, 1500000)
        stage = random.choice(stages)
        probability = {
            "Prospecting": 10,
            "Qualification": 20,
            "Needs Analysis": 40,
            "Value Proposition": 60,
            "Proposal/Price Quote": 75,
            "Negotiation/Review": 90,
        }[stage]

        close_date = datetime.now() + timedelta(days=random.randint(30, 180))

        try:
            result = sf.Opportunity.create(
                {
                    "Name": f"{product_name} - {accounts[i]['Name'][:20]}",
                    "AccountId": account_id,
                    "StageName": stage,
                    "Amount": amount,
                    "Probability": probability,
                    "CloseDate": close_date.strftime("%Y-%m-%d"),
                }
            )
            opp_count += 1
            print(f"  ✓ Opp {opp_count}: ${amount:,} ({stage})")
        except Exception as e:
            print(f"  ✗ Opportunity creation failed: {e}")

print(f"\n✓ Created {opp_count} opportunities")

print("\n" + "=" * 60)
print("DATA UPLOAD COMPLETE!")
print("=" * 60)
print(f"Products:      {len(product_ids)}")
print(f"Accounts:      {len(account_ids)}")
print(f"Contracts:     {contract_count}")
print(f"Opportunities: {opp_count}")
print("=" * 60)
