import os
import re
import json
import pdfplumber

# Load metadata from meta.json
with open("meta.json", "r") as meta_file:
    META = json.load(meta_file)

REBOOT_PHRASES = [
    "reboot may be required", "requires a restart", "restart the device",
    "reboot the computer", "reboot the system", "restart your machine",
    "reboot is needed", "reboot required", "does not take effect until the next reboot",
]

TERMINATION_KEYWORDS = ["Default Value", "Impact", "Audit:", "References:"]

def normalize_text(text):
    """
    Normalize text by removing policy numbers and page references.
    """
    text = re.sub(r'\d+\.\d+\.\d+|\d+\.\d+|Page \d+', '', text)  # Remove policy numbers and page references
    return text.strip().lower()

def remove_duplicates(deltas):
    """
    Remove duplicate policies from the delta list.
    Compare normalized policy descriptions and remediations.
    """
    unique_deltas = []
    seen_content = set()

    for delta in deltas:
        # Normalize text for comparison
        normalized_desc = normalize_text(delta["Policy Description"])
        normalized_rem = normalize_text(delta["Remediation"])

        # Combine normalized description and remediation for unique comparison
        combined_content = f"{normalized_desc} {normalized_rem}"

        if combined_content not in seen_content:
            seen_content.add(combined_content)
            unique_deltas.append(delta)

    return unique_deltas

def infer_category(remediation):
    if remediation:
        remediation_lower = remediation.lower()
        if "group policy" in remediation_lower or "computer configuration" in remediation_lower:
            return "GPO"
        elif "registry" in remediation_lower or "hkey_" in remediation_lower:
            return "Registry Settings"
        return "Other"
    return "Unknown"

def extract_path_and_setting(remediation_text):
    remediation_text = re.sub(r"\s+", " ", remediation_text.strip())

    # Extract Path
    path_match = re.search(
        r"(Computer Configuration|User Configuration).*?(?=\s*(Default Value|References|CIS Controls|Page|$))",
        remediation_text, re.IGNORECASE | re.DOTALL
    )
    path = path_match.group(0).strip() if path_match else "Unknown"

    # Extract Setting from "set the following UI path to <VALUE>" or similar patterns
    setting_match = re.search(
        r"set the following UI path to\s*['\"]?([^:.]+)['\"]?",
        remediation_text, re.IGNORECASE
    )
    setting = setting_match.group(1).strip() if setting_match else "Unknown"

    return path, setting

def detect_reboot_requirement(text):
    for phrase in REBOOT_PHRASES:
        if re.search(re.escape(phrase), text, re.IGNORECASE):
            return True
    return False

def extract_policies_with_remediation(pdf_path):
    policies = []
    policies_list = []
    current_policy = {}
    remediation_buffer = []
    capturing_remediation = False
    capturing_description = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split("\n"):
                line = line.strip()
                if re.match(r"^\d+\.\d+.*(Ensure|Configure).*", line):
                    if current_policy and remediation_buffer:
                        remediation_text = " ".join(remediation_buffer).strip()
                        for term in TERMINATION_KEYWORDS:
                            remediation_text = remediation_text.split(term)[0].strip()
                            remediation_text = re.sub(r'Page \d+$', '', remediation_text).strip()
                        current_policy["Remediation"] = remediation_text
                        current_policy["Category"] = infer_category(remediation_text)
                        current_policy["Path"], current_policy["Setting"] = extract_path_and_setting(remediation_text)
                        current_policy["Reboot_required"] = detect_reboot_requirement(remediation_text)
                        current_policy["Enabled"] = True
                        current_policy["Ignore"] = False
                        policies.append(current_policy)
                        policies_list.append({"Policy Description": current_policy["Policy Description"]})
                        remediation_buffer = []
                    current_policy = {"Policy Description": line}
                    #for multiline description capturing_description value will be true.
                    capturing_description = not (re.search(r"\(Automated\)$", line, re.IGNORECASE) or re.search(r"\(Manual\)$", line, re.IGNORECASE))
                    if "(Automated)" in line:
                        current_policy["Policy Description"] = line.split("(Automated)")[0].strip() + " (Automated)"
                    elif "(Manual)" in line:
                        current_policy["Policy Description"] = line.split("(Manual)")[0].strip() + " (Manual)"
                    capturing_remediation = False
                elif capturing_remediation or "Remediation:" in line:
                    capturing_remediation = True
                    remediation_buffer.append(line.replace("Remediation:", "").strip())
                    if any(term in line for term in TERMINATION_KEYWORDS):
                        capturing_remediation = False
                    #below condition will execute for multiline policy descriptions only.    
                elif capturing_description:
                    if "Policy Description" not in current_policy:
                        current_policy["Policy Description"] = ""
                    current_policy["Policy Description"] += f" {line}"
                    if re.search(r"\(Automated\)$", current_policy["Policy Description"], re.IGNORECASE) or re.search(r"\(Manual\)$", current_policy["Policy Description"], re.IGNORECASE):
                        if "(Automated)" in current_policy["Policy Description"]:
                            current_policy["Policy Description"] = current_policy["Policy Description"].split("(Automated)")[0].strip() + " (Automated)"
                        elif "(Manual)" in current_policy["Policy Description"]:
                            current_policy["Policy Description"] = current_policy["Policy Description"].split("(Manual)")[0].strip() + " (Manual)"
                        capturing_description = False

    if current_policy and remediation_buffer:
        remediation_text = " ".join(remediation_buffer).strip()
        for term in TERMINATION_KEYWORDS:
            remediation_text = remediation_text.split(term)[0].strip()
            remediation_text = re.sub(r'Page \d+$', '', remediation_text).strip()
        current_policy["Remediation"] = remediation_text
        current_policy["Category"] = infer_category(remediation_text)
        current_policy["Path"], current_policy["Setting"] = extract_path_and_setting(remediation_text)
        current_policy["Reboot_required"] = detect_reboot_requirement(remediation_text)
        current_policy["Enabled"] = True
        current_policy["Ignore"] = False
        policies.append(current_policy)
        policies_list.append({"Policy Description": current_policy["Policy Description"]})
        
    return policies, policies_list


def normalize_policy_text(policy_text):
    """
    Remove dynamic elements like policy numbers and page numbers from policy text.
    """
    # Remove policy numbers (e.g., 2.2.7, 18.4.5)
    text = re.sub(r"^\d+(\.\d+)*", "", policy_text).strip()
    # Remove page references (e.g., Page 123)
    text = re.sub(r"Page \d+", "", text).strip()
    return text

def compare_policies(old_policies, new_policies):
    """
    Compare old and new policies, identifying added, removed, and updated entries.
    """
    added = []
    removed = []
    updated = []

    # Normalize and index old and new policies by their content
    old_index = {
        (normalize_policy_text(policy.get("Policy Description", "")),
         normalize_policy_text(policy.get("Remediation", ""))): policy
        for policy in old_policies
    }
    new_index = {
        (normalize_policy_text(policy.get("Policy Description", "")),
         normalize_policy_text(policy.get("Remediation", ""))): policy
        for policy in new_policies
    }

    # Identify added and updated policies
    for key, new_policy in new_index.items():
        if key not in old_index:
            added.append(new_policy)
        elif old_index[key] != new_policy:
            updated.append({"old": old_index[key], "new": new_policy})

    # Identify removed policies
    for key, old_policy in old_index.items():
        if key not in new_index:
            removed.append(old_policy)

    return {"added": added, "removed": removed, "updated": updated}

def save_to_json(data, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def main():
    input_pdf = META["input_pdf"]
    output_folder = META["output_folder"]
    policies_output = os.path.join(output_folder, META["policies_output"])
    policies_list_output = os.path.join(output_folder, META["index_output"])
    delta_output = os.path.join(output_folder, "delta_policies.json")
    inventory_folder = META["inventory_folder"]

    print(f"Processing PDF: {input_pdf}")

    previous_policies_file = None
    for file in os.listdir(inventory_folder):
        if file.startswith("policies_with_remediation") and file.endswith(".json"):
            previous_policies_file = os.path.join(inventory_folder, file)
            break

    if previous_policies_file:
        print(f"Found previous version: {previous_policies_file}")
        with open(previous_policies_file, "r") as f:
            old_policies = json.load(f)

        new_policies, policies_list = extract_policies_with_remediation(input_pdf)
        deltas = compare_policies(old_policies, new_policies)

        # Remove duplicates from the delta
        deltas["added"] = remove_duplicates(deltas["added"])

        save_to_json(deltas, delta_output)
        print(f"Delta policies saved to: {delta_output}")

    else:
        print("No previous version found. Processing current PDF only.")
        new_policies, policies_list = extract_policies_with_remediation(input_pdf)

    save_to_json(new_policies, policies_output)
    save_to_json(policies_list, policies_list_output)
    print(f"Policies saved to: {policies_output}")
    print(f"Policies list saved to: {policies_list_output}")

if __name__ == "__main__":
    main()
