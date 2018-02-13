"""
    This file made available under CC0 1.0 Universal
    (https://creativecommons.org/publicdomain/zero/1.0/legalcode)

    Description: Check that security groups prefixed with "launch-wizard"
              are not associated with network interfaces.

    Trigger Type: Change Triggered
    Scope of Changes: EC2:NetworkInterface
    Accepted Parameters: None
    Your Lambda function execution role will need to have a policy that provides
    the appropriate permissions. Here is a policy that you can consider.
    You should validate this for your own environment.

    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "config:PutEvaluations"
                ],
                "Resource": "*"
            }
        ]
    }
"""
import logging
import json
import boto3

LOG = logging.getLogger()
LOG.setLevel(logging.INFO)

APPLICABLE_RESOURCES = ['AWS::EC2::NetworkInterface']
AWS_CONFIG = boto3.client('config')


def evaluate_compliance(configuration_item):
    """
        Evaluate Compliance of the Configuration Item
    """

    # Start as compliant
    compliance_type = 'COMPLIANT'
    annotation = 'Resource is compliant.'

    # Check resource for applicability
    if configuration_item['resourceType'] not in APPLICABLE_RESOURCES:
        compliance_type = 'NOT_APPLICABLE'
        annotation = "The rule doesn't apply to resources of type " \
                     + configuration_item['resourceType'] + '.'

    # Iterate over security groups
    for security_group in configuration_item['configuration']['groups']:
        if 'launch-wizard' in security_group['groupName']:
            compliance_type = 'NON_COMPLIANT'
            annotation = 'A launch-wizard security group ' \
                         'is attached to ' \
                         + configuration_item['configuration']['privateIpAddress']
            break

    return {
        'compliance_type': compliance_type,
        'annotation': annotation
    }


def lambda_handler(event, _):
    """ Lambda Handler """

    LOG.debug('Event %s', event)

    invoking_event = json.loads(event['invokingEvent'])
    configuration_item = invoking_event['configurationItem']
    evaluation = evaluate_compliance(configuration_item)

    LOG.info(
        'Compliance evaluation for %s: %s',
        configuration_item['resourceId'],
        evaluation['compliance_type'])
    LOG.info('Annotation: %s', evaluation['annotation'])

    AWS_CONFIG.put_evaluations(
        Evaluations=[
            {
                'ComplianceResourceType': invoking_event['configurationItem']['resourceType'],
                'ComplianceResourceId': invoking_event['configurationItem']['resourceId'],
                'ComplianceType': evaluation['compliance_type'],
                'Annotation': evaluation['annotation'],
                'OrderingTimestamp':
                    invoking_event['configurationItem']['configurationItemCaptureTime']
            },
        ],
        ResultToken=event['resultToken'])
