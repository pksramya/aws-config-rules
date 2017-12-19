#
# This file made available under CC0 1.0 Universal (https://creativecommons.org/publicdomain/zero/1.0/legalcode)
#
# Ensure that no security groups allow public access to the specified ports.
# Description: Checks that all security groups block access to the specified ports and removes ip permissions that violate the rule.
#
# Trigger Type: Change Triggered
# Scope of Changes: EC2:SecurityGroup
# Accepted Parameters: examplePort1, exampleRange1, examplePort2, ...
# Example Value: 8080, 1-1024, 2375, ...


import json
import boto3
import botocore



APPLICABLE_RESOURCES = ["AWS::EC2::SecurityGroup"]

def capitalize(x):
   if isinstance(x, list):
     return [capitalize(v) for v in x]
   elif isinstance(x, dict):
     return {k[0].upper() + k[1:]: capitalize(v) for k, v in x.items()}
   else:
     return x

def expand_range(ports):
    if "-" in ports:
        return range(int(ports.split("-")[0]), int(ports.split("-")[1])+1)
    else:
        return [int(ports)]

def revoke_permissions(permissions):
    #global group_id
    group_id = configuration_item["configuration"]["groupId"]
    client = boto3.client("ec2");
    print("revoking permissions in ", group_id)
    #Capatilize the first letter of each key
    revoke_permissions = [capitalize(permission)]
    #Transform Ipv4Ranges -> IpRanges
    for element in revoke_permissions: 
        #dictionary[new_key] = dictionary.pop(old_key)
        element["IpRanges"] = element.pop("Ipv4Ranges")
        print("input for revoke permissions: " + str(revoke_permissions))
        try:
            client.revoke_security_group_ingress(GroupId=group_id, IpPermissions=revoke_permissions)
            return {
                "compliance_type" : "NON_COMPLIANT",
                "annotation" : " revoking: " + str(revoke_permissions)
            }
        except botocore.exceptions.ClientError as e:
            print (e)
            return {
                "compliance_type" : "NON_COMPLIANT",
                "annotation" : "revoke_security_group_ingress error " + e
            }
                
def find_exposed_ports(ip_permissions):
    exposed_ports = []
    global permission
    for permission in ip_permissions or []:
        for cidrIpv6 in permission["ipv6Ranges"]:
            if "::/0" in cidrIpv6["cidrIpv6"]:
                print("ipv6 detected")
                print("Violating ipv 6 Permission: ", json.dumps(capitalize(permission), indent=2))
                normal = json.dumps(capitalize(permission), indent=2)
                revoke = revoke_permissions(normal) 
                if "fromPort" in permission:
                        exposed_ports.extend(range(permission["fromPort"],
                                                   permission["toPort"]+1))
                # if "fromPort" does not exist, port range is "All"
                else:
                    exposed_ports.extend(range(0,65535+1))
                    
    for permission in ip_permissions or []:
        for cidrIp in permission["ipRanges"]:
            if "0.0.0.0/0" in cidrIp:
                print("ipv4 detected")
                print("Violating ipv 4 Permission: ", json.dumps(capitalize(permission), indent=2))
                normal = json.dumps(capitalize(permission), indent=2)
                revoke = revoke_permissions(normal) 
                if "fromPort" in permission:
                        exposed_ports.extend(range(permission["fromPort"],
                                                   permission["toPort"]+1))
                # if "fromPort" does not exist, port range is "All"
                else:
                    exposed_ports.extend(range(0,65535+1))
                    
    return exposed_ports


def find_violation(ip_permissions, forbidden_ports):
    exposed_ports = find_exposed_ports(ip_permissions)
    for forbidden in forbidden_ports:
        ports = expand_range(forbidden_ports[forbidden])
        for port in ports:
            if port in exposed_ports:
                return "A forbidden port is exposed to the internet."

    return None


def evaluate_compliance(configuration_item, rule_parameters):
    if configuration_item["resourceType"] not in APPLICABLE_RESOURCES:
        return {
            "compliance_type": "NOT_APPLICABLE",
            "annotation": "The rule doesn't apply to resources of type " +
            configuration_item["resourceType"] + "."
        }

    # Check if resource was deleted
    if configuration_item['configurationItemStatus'] == "ResourceDeleted":
        return {
            "compliance_type": "NOT_APPLICABLE",
            "annotation": "This resource was deleted."
        }

    violation = find_violation(
        configuration_item["configuration"].get("ipPermissions"),
        rule_parameters
    )

    if violation:
        return {
                "compliance_type": "NON_COMPLIANT",
                "annotation": violation
            }
    return {
        "compliance_type": "COMPLIANT",
        "annotation": "This resource is compliant with the rule."
    }


def lambda_handler(event, context):
    invoking_event = json.loads(event["invokingEvent"])
    global configuration_item
    configuration_item = invoking_event["configurationItem"]
    rule_parameters = json.loads(event["ruleParameters"])

    result_token = "No token found."
    if "resultToken" in event:
        result_token = event["resultToken"]

    evaluation = evaluate_compliance(configuration_item, rule_parameters)

    config = boto3.client("config")
    config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType":
                    configuration_item["resourceType"],
                "ComplianceResourceId":
                    configuration_item["resourceId"],
                "ComplianceType":
                    evaluation["compliance_type"],
                "Annotation":
                    evaluation["annotation"],
                "OrderingTimestamp":
                    configuration_item["configurationItemCaptureTime"]
            },
        ],
        ResultToken=result_token
    )
