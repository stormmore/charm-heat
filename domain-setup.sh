#!/bin/bash

set -e

openstack domain create --description "Stack projects and users" heat

openstack user create --domain heat --password `leader-get heat-domain-admin-passwd` heat_domain_admin

openstack role add --domain heat --user heat_domain_admin admin

openstack role create heat_stack_user
