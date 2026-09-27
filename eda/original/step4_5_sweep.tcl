source ./script/common_setup.tcl

set top $::env(STEP4_5_TOP)
set corner $::env(STEP4_5_CORNER)
set setup_unc $::env(STEP4_5_SETUP_UNC)
set hold_unc $::env(STEP4_5_HOLD_UNC)
set skew $::env(STEP4_5_SKEW)
set tag "${top}_${corner}_su${setup_unc}_hu${hold_unc}_sk${skew}"

if {$corner == "SS"} {
  set lib saed32rvt_ss0p95v125c.db
} else {
  set lib saed32rvt_ff1p16v125c.db
}

set netlist ${DC_DATA_PATH}/step4_5/${top}_${corner}/results/${top}.mapped.v
set report_dir ./rpt/step4_5
file mkdir $report_dir

set_app_var search_path ". $std_library_path $search_path"
set_app_var link_library "* $lib"
read_verilog $netlist
current_design $top
link

if {$top == "step4_5_scan_ff_only" || $top == "step4_5_scan_mux_ff"} {
  create_clock -period 10.0 -waveform {0 5} -name CLK_MAIN [get_ports clk_scan]
  set clock_port [get_ports clk_scan]
} else {
  create_clock -period 20.0 -waveform {0 10} -name CLK_MAIN [get_ports clk_spare]
  set clock_port [get_ports clk_spare]
}
set_clock_uncertainty -setup $setup_unc [get_clocks CLK_MAIN]
set_clock_uncertainty -hold $hold_unc [get_clocks CLK_MAIN]
set_clock_latency -source 0.0 [get_clocks CLK_MAIN]
set_ideal_network $clock_port

if {$top == "step4_5_scan_mux_ff"} {
  set_case_analysis 1 [get_ports se]
}

if {$top == "step4_5_spare_forced_lockup"} {
  create_generated_clock -name CLK_LOCKUP -source [get_ports clk_spare] -divide_by 1 -invert \
    [get_pins u_lockup_clk_inv/Y]
  set_clock_latency -source $skew [get_clocks CLK_LOCKUP]
  set_clock_uncertainty -setup $setup_unc [get_clocks CLK_LOCKUP]
  set_clock_uncertainty -hold $hold_unc [get_clocks CLK_LOCKUP]
}

update_timing

set all_seq [all_registers]
if {$top == "step4_5_spare_forced_lockup"} {
  set latch_seq [get_cells -hierarchical -filter "ref_name =~ LATCH*"]
} else {
  set latch_seq [remove_from_collection $all_seq $all_seq]
}
set ff_seq [remove_from_collection $all_seq $latch_seq]

proc worst_slack {from_obj to_obj delay_type} {
  if {[sizeof_collection $from_obj] == 0 || [sizeof_collection $to_obj] == 0} {
    return "NA"
  }
  set paths [get_timing_paths -from $from_obj -to $to_obj -delay_type $delay_type -nworst 1]
  if {[sizeof_collection $paths] == 0} {
    return "NA"
  }
  return [format "%.4f" [get_attribute [index_collection $paths 0] slack]]
}

set ff_setup [worst_slack $ff_seq $ff_seq max]
set ff_hold [worst_slack $ff_seq $ff_seq min]
set ff_to_latch_setup [worst_slack $ff_seq $latch_seq max]
set ff_to_latch_hold [worst_slack $ff_seq $latch_seq min]
set latch_to_ff_setup [worst_slack $latch_seq $ff_seq max]
set latch_to_ff_hold [worst_slack $latch_seq $ff_seq min]

set out [open "${report_dir}/${tag}.csv" w]
puts $out "top,corner,setup_unc,hold_unc,lockup_skew,ff_count,latch_count,ff_setup,ff_hold,ff_to_latch_setup,ff_to_latch_hold,latch_to_ff_setup,latch_to_ff_hold"
puts $out "$top,$corner,$setup_unc,$hold_unc,$skew,[sizeof_collection $ff_seq],[sizeof_collection $latch_seq],$ff_setup,$ff_hold,$ff_to_latch_setup,$ff_to_latch_hold,$latch_to_ff_setup,$latch_to_ff_hold"
close $out

report_timing -from $ff_seq -to $ff_seq -delay_type max -max_paths 3 -slack_lesser_than 100000 -nosplit > "${report_dir}/${tag}.ff_setup.rpt"
report_timing -from $ff_seq -to $ff_seq -delay_type min -max_paths 3 -slack_lesser_than 100000 -nosplit > "${report_dir}/${tag}.ff_hold.rpt"
if {[sizeof_collection $latch_seq] > 0} {
  report_timing -from $ff_seq -to $latch_seq -delay_type max -max_paths 3 -slack_lesser_than 100000 -nosplit > "${report_dir}/${tag}.ff_to_latch_setup.rpt"
  report_timing -from $ff_seq -to $latch_seq -delay_type min -max_paths 3 -slack_lesser_than 100000 -nosplit > "${report_dir}/${tag}.ff_to_latch_hold.rpt"
  report_timing -from $latch_seq -to $ff_seq -delay_type max -max_paths 3 -slack_lesser_than 100000 -nosplit > "${report_dir}/${tag}.latch_to_ff_setup.rpt"
  report_timing -from $latch_seq -to $ff_seq -delay_type min -max_paths 3 -slack_lesser_than 100000 -nosplit > "${report_dir}/${tag}.latch_to_ff_hold.rpt"
}
check_timing -verbose > "${report_dir}/${tag}.check_timing.rpt"
exit
