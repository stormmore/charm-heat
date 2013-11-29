Overview
========

Heat is the main project in the OpenStack Orchestration program. It implements 
an orchestration engine to launch multiple composite cloud applications based 
on templates in the form of text files that can be treated like code.

This charm deploys the Heat infrastructure.

Usage
=====

Heat requires the existence of the other core OpenStack services deployed via
Juju charms, specifically: mysql, rabbitmq-server, keystone and
nova-cloud-controller. The following assumes these services have already
been deployed.

Contact Information
===================

Author: Yolanda Robla <yolanda.robla@canonical.com>
Report bugs at: http://bugs.launchpad.net/charms/+source/heat/+filebug
Location: http://jujucharms.com/charms/heat
