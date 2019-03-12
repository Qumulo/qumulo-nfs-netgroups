# qumulo_netgroup_nfs
Apply NIS Netgroup restrictions on Qumulo NFS Exports

Assumptions:

- The machine running this script is joined to an NIS domain
- The netgroup hosts are all in the default NIS domain
- The map format is something like "(host1,,) (host2,,) (host3,,) (host4,,)"
    - The user and domain fields are ignored

Issues:

- Netgroups are enumerated for each share as they are modified. This is
  inefficient for large netgroups.

