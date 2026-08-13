# Information Security Policy

## Overview

The AcmeCorp Information Security Policy establishes the controls and
responsibilities that protect company information and customer data. It applies
to all employees, contractors, and third parties with access to AcmeCorp systems.

## Access Control

### Account Provisioning

Access is granted on a least-privilege basis. Every request must name an owner
and an approver. Accounts are reviewed quarterly, and access to terminated
employees is revoked within 24 hours of separation.

### Passwords and Multi-Factor Authentication

Passwords must be at least 14 characters and unique per service. Multi-factor
authentication is mandatory for all accounts with access to production data.
Password resets require verification through a secondary channel.

## Data Classification

Company data is classified into three tiers: Public, Internal, and Confidential.
Confidential data includes customer personal information, source code, and
financial records. Confidential data may only be processed in approved,
encrypted storage and is never transmitted over unencrypted channels.

## Data Retention

Retention periods are defined per data class. Customer personal information is
retained for the duration of the service contract plus 12 months, after which it
must be deleted or anonymized. Backups follow the same schedule and are retained
for no longer than the retention period of the source data.

## Incident Reporting

Any suspected breach of this policy must be reported to security-oncall within
one hour. Reporting channels include the security mailbox, the on-call phone
line, and the internal chat security channel. No disciplinary action applies to
good-faith reporting.

## Remote Access

Remote access to the corporate network requires a managed device, the approved
VPN, and MFA. Personal devices are not permitted to access production systems.

## Compliance

Violations of this policy may result in disciplinary action up to and including
termination. Questions about the policy should be directed to the Security team
before action is taken, not after.
