# qumulo-nfs-netgroups
Apply NIS Netgroup restrictions on Qumulo NFS Exports

Assumptions:

- Exports specified in the configuration file, already exist on the cluster.
- The machine running this script is joined to an NIS domain
- The netgroup hosts are all in the default NIS domain
- The map format is something like "(host1,,) (host2,,) (host3,,) (host4,,)"
    - The user and domain fields are ignored

Recommendations:

- Consider running this automatically on your NIS master when maps are updated.

Issues:

- Netgroups are enumerated for each share as they are modified. This is
  inefficient for large netgroups.

