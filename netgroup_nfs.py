#!/usr/bin/env python

import argparse
import json
import logging as log
from pprint import pprint, pformat
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
        log.warning("{} failed to resolve: {}".format(hostname, error))
        return []

def parse_net_group(netgroup):
    """
    Returns a list netgroup hosts
    """
    try:
        raw_netgroup = nis.cat('netgroup')[netgroup]
    except Exception as error:
        log.error("FAILED to reteive netgroup map from NIS server: {}".format(
            error))
        log.error("Does 'ypcat netgroup' return a map?")
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
    for netgroup in allowed_hosts['netgroups']:
        for hostname in parse_net_group(netgroup):
            # Merge and de-duplicate newly returned IPs
            ips = list(set().union(ips, get_ips(hostname)))
    for host in allowed_hosts['hosts']:
        ips = list(set().union(ips, get_ips(host)))
    return ips

def parse_config(config_json):
    """
    Parse our configuration json
    """
    try:
        with open(config_json) as config_file:
            return json.load(config_file)
    except Exception as error:
        log.error("FAILED to open {}: {}".format(config_json, error))
        raise

def main():

    parser = argparse.ArgumentParser(
        description='Add NFS export restrictions from netgroups to a cluster')
    parser.add_argument('--config', default='netgroup_nfs.json',
                        help='Config json filename.')
    parser.add_argument('--commit', action='store_true',
                        help='Apply restrictions to cluster.')
    parser.add_argument('--verbose', '-v', action='count',
                        help='Increase verbosity of messages.')
    args = parser.parse_args()


    if args.verbose == 1:
        loglevel=log.INFO
    elif args.verbose > 1:
        loglevel=log.DEBUG
    else:
        loglevel=log.WARN

    log.basicConfig(format="%(levelname)s: %(message)s", level=loglevel)

    options = parse_config(args.config)

    # Connect to Cluster Rest API
    restclient = qumulo.rest_client.RestClient(options['hostname'], 8000)
    try:
        log.info("Logging into {hostname} as user {username}".format(**options))
        restclient.login(options['username'], options['password'])
    except:
        log.error("FAILED to login to cluster at {hostname}".format(**options))
        raise

    export_map = options['export_map']

    for export_path in export_map.keys():
        # Retrieve the current export configuration
        try:
            export = restclient.nfs.nfs_get_export(export_path)
        except qumulo.lib.request.RequestError as error:
            log.warning("Failure to retrieve export for {}: {}".format(
                export_path, error))
            continue

        # We don't appear to use more than one set of export restrictions, but
        # just in case...
        if len(export['restrictions']) > 1:
            log.error("This script cannot currently handle exports that "
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
        if args.commit:
            log.info("Updating export ({})".format(export_path))
            update_result = restclient.nfs.nfs_modify_export(**export)
            log.debug("{}\n".format(pformat(update_result)))
        else:
            log.debug("Unapplied export configuration ({})".format(export_path))
            log.debug("{}\n".format(pformat(export)))

    if not args.commit:
        log.info("No configuration applied. Use --commit to apply changes.")

if __name__ == '__main__':
    main()
