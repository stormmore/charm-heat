Overview
========

Heat is the main project in the OpenStack Orchestration program. It implements 
an orchestration engine to launch multiple composite cloud applications based 
on templates in the form of text files that can be treated like code.

This charm deploys the Heat infrastructure.

Usage
=====

The ceph charm has two pieces of mandatory configuration for which no defaults
are provided:

    fsid:
        uuid specific to a ceph cluster used to ensure that different
        clusters don't get mixed up - use `uuid` to generate one.

    monitor-secret: 
        a ceph generated key used by the daemons that manage to cluster
        to control security.  You can use the ceph-authtool command to 
        generate one:

            ceph-authtool /dev/stdout --name=mon. --gen-key

These two pieces of configuration must NOT be changed post bootstrap; attempting
to do this will cause a reconfiguration error and new service units will not join
the existing ceph cluster.

The charm also supports the specification of storage devices to be used in the
ceph cluster.

    osd-devices:
        A list of devices that the charm will attempt to detect, initialise and
        activate as ceph storage.

        This can be a superset of the actual storage devices presented to each
        service unit and can be changed post ceph bootstrap using `juju set`.

        The full path of each device must be provided, e.g. /dev/vdb.

        For Ceph >= 0.56.6 (Raring or the Grizzly Cloud Archive) use of
        directories instead of devices is also supported.

At a minimum you must provide a juju config file during initial deployment
with the fsid and monitor-secret options (contents of cepy.yaml below):

    ceph:
        fsid: ecbb8960-0e21-11e2-b495-83a88f44db01 
        monitor-secret: AQD1P2xQiKglDhAA4NGUF5j38Mhq56qwz+45wg==
        osd-devices: /dev/vdb /dev/vdc /dev/vdd /dev/vde

Specifying the osd-devices to use is also a good idea.

Boot things up by using:

    juju deploy -n 3 --config ceph.yaml ceph

By default the ceph cluster will not bootstrap until 3 service units have been
deployed and started; this is to ensure that a quorum is achieved prior to adding
storage devices.

Contact Information
===================

Author: Yolanda Robla <yolanda.robla@canonical.com>
Report bugs at: http://bugs.launchpad.net/charms/+source/heat/+filebug
Location: http://jujucharms.com/charms/heat
