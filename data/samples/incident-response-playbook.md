# Incident Response Playbook

## Purpose and Scope

This playbook defines the procedure for detecting, responding to, and recovering
from security incidents at AcmeCorp. It applies to all production systems,
corporate endpoints, and customer data. Every incident has an owner and follows a
fixed set of phases: Triage, Containment, Eradication, Recovery, and Lessons
Learned.

## Roles

### Incident Commander

The Incident Commander owns the incident end to end, coordinates teams, and is the
single point of communication with leadership. This role rotates weekly and is
always held by a member of the Security team.

### Communications Lead

The Communications Lead drafts internal and external messaging. External breach
notifications must be reviewed by Legal before any message is sent to customers
or regulators.

## Triage and Classification

Every report enters triage within 15 minutes of receipt. Severity is classified
as SEV-1 (data breach or production outage), SEV-2 (significant degradation), or
SEV-3 (localized issue). SEV-1 incidents require an incident commander, a war
room, and a status update every 30 minutes.

## Containment and Eradication

Containment begins by isolating affected hosts and rotating credentials for any
accounts that may have been exposed. Eradication removes the root cause and
confirms the adversary no longer has access. Evidence must be preserved in the
forensic evidence vault before any remediation action is taken.

## Recovery and Lessons Learned

Services return to production only after validation checks pass and the change is
approved by the incident commander. Within 30 days of closure, a Lessons Learned
review produces an action list with owners and deadlines.

## Key Contacts

- Security on-call: security-oncall@acmecorp.example
- Compliance: compliance@acmecorp.example
- Legal: legal@acmecorp.example
