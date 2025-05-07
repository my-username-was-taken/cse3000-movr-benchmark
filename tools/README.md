# Running a scenario using Python scripts

Disclaimer: These instructions have only been tested in an ST cluster setup.

1. Activate the environment `cd Detock/ && source build_detock/bin/activate`
2. Spin up the cluster (make sure your conf file has the correct partitioning) `python3 tools/admin.py start --image omraz/seq_eval:latest examples/tu_cluster.conf -u omraz -e GLOG_v=1`
3. Check the status for any errors `python3 tools/admin.py status --image omraz/seq_eval:latest examples/tu_cluster.conf -u omraz`
4. Run a single scenario (you will have to tweak this script to work for your scenario) `python3 tools/run_config_on_remote.py -s [scenario] -w [workload]` (see file for full list of params)
5. Process the resutls (you will have to tweak this script to work for your scenario) `python3 plots/extract_exp_results.py -s [scenario] -w [workload]`

This should produce your plots.

