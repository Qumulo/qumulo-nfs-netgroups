#!/usr/bin/env python

import argparse
import json
import pprint
import re
import socket
import nis

import qumulo.rest_client
from qumulo.rest.nfs import NFSExportRestriction

def get_ips(hostname):
    """
    Returns an array containing all of the IPs for a hostname
    """
    try:
        data = socket.gethostbyname_ex(hostname)
        return data[2]
    except socket.gaierror as error:
        # ignore resolution failures
        print "WARNING! {} failed to resolve: {}".format(hostname, error)
        return []

def parse_net_group(netgroup):
    """
    Returns a list netgroup hosts
    """
    try:
        raw_netgroup = nis.cat('netgroup')[netgroup]
    except Exception as error:
        print "FAILED to reteive netgroup map from NIS server: {}".format(
            error)
        print "Does 'ypcat netgroup' return a map?"
        raise
    allhosts = []
    # Expecting input format of: "(red,,) (green,,) (blue,,)"
    hosts=re.findall(r"\((\S+),\S*,\S*", raw_netgroup)
    # Expecting input format of "all servers workstations", strip any hosts
    stripped_groups = re.findall(r'([^(\)]+)(?:$|\()', raw_netgroup)
    # Expecting input format of "all servers workstations"
    groups=re.findall(r"(\S+)\s", stripped_groups[0])
    allhosts = list(set().union(allhosts, hosts))
    for group in groups:
        # Recurse into specified groups, and merge the returned hosts
        allhosts = list(set().union(allhosts, parse_net_group(group)))
    return allhosts

def enumerate_hosts(allowed_hosts):
    """
    Returns an enumerated list of IPs from a netgroup
    """
    ips = []
    for netgroup in allowed_hosts:
        for hostname in parse_net_group(netgroup):
            # Merge and de-duplicate newly returned IPs
            ips = list(set().union(ips, get_ips(hostname)))
    return ips

def parse_config(config_json):
    """
    Parse our configuration json
    """
    try:
        with open(config_json) as config_file:
            return json.load(config_file)
    except Exception as error:
        print "FAILED to open {}: {}".format(config_json, error)
        raise

def main():

    parser = argparse.ArgumentParser(
        description='Add NFS export restrictions from netgroups to a cluster')
    parser.add_argument('--config', default="netgroup_nfs.json")
    args = parser.parse_args()

    options = parse_config(args.config)

    # Connect to Cluster Rest API
    restclient = qumulo.rest_client.RestClient(options['hostname'], 8000)
    try:
        print "Logging into {hostname} as user {username}".format(**options)
        restclient.login(options['username'], options['password'])
    except:
        print "FAILED to login to cluster at {hostname}".format(**options)
        raise

    export_map = options['export_map']

    for export_path in export_map.keys():
        # Retrieve the current export configuration
        try:
            export = restclient.nfs.nfs_get_export(export_path)
        except qumulo.lib.request.RequestError as error:
            print "WARNING! Failure to retrieve export for {}: {}".format(
                export_path, error)
            continue

        # We don't appear to use more than one set of export restrictions, but
        # just in case...
        if len(export['restrictions']) > 1:
            print("ERROR! This script cannot currently handle exports that "
                  "have more than one restriction list.")
            raise Exception

        allowed_hosts = export_map[export_path]

        # Define IP restrictions for the enumerated netgroups
        export['restrictions'][0]['host_restrictions'] = enumerate_hosts(
                                                            allowed_hosts)

        # Manipulate our configuration so that we can modify the export
        export['restrictions'][0] = NFSExportRestriction(
                                        export['restrictions'][0])
        export[u'id_'] = export.pop('id')

        # Apply our changes to this export
        print "Updating export ({}):".format(export_path)
        pprint.pprint(restclient.nfs.nfs_modify_export(**export))
        print ""

if __name__ == '__main__':
    main()
