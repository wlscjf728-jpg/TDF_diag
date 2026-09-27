source ../../common_setup.tcl

# Usage:
#   env NEW_BENCH=mor1kx    dc_shell -f new_bench_baseline_synth.tcl
#   env NEW_BENCH=aes_secworks dc_shell -f new_bench_baseline_synth.tcl

if {![info exists ::env(NEW_BENCH)]} {
  echo "NEW_BENCH must be mor1kx or aes_secworks"
  exit 2
}

set BENCH $::env(NEW_BENCH)
set NEW_BENCH_ROOT "${PJT_PATH}/RTL"

switch -- $BENCH {
  mor1kx {
    set TOP mor1kx
    set CLOCK_PORT clk
    # Include all RTL files EXCEPT the behavioral DPRAM files;
    # use stub instead so DC treats memories as black boxes.
    set RTL_FILES [list]
    foreach f [glob ${NEW_BENCH_ROOT}/mor1kx/*.v] {
      if {[string match "*mor1kx_simple_dpram_sclk.v" [file tail $f]]} { continue }
      if {[string match "*mor1kx_true_dpram_sclk.v"  [file tail $f]]} { continue }
      if {[string match "*espresso*" [file tail $f]]} { continue }
      lappend RTL_FILES $f
    }
    foreach f [glob ${NEW_BENCH_ROOT}/mor1kx/pfpu32/*.v] {
      lappend RTL_FILES $f
    }
    # mor1kx parameters: cappuccino pipeline, both caches enabled
    # WORKAROUND: Removed FEATURE_FPU=NONE as instructed in the worker prompt to prevent elaboration failures.
    set ELAB_PARAMS "OPTION_CPU0=\"CAPPUCCINO\",FEATURE_DATACACHE=\"ENABLED\",FEATURE_INSTRUCTIONCACHE=\"ENABLED\",FEATURE_DMMU=\"NONE\",FEATURE_IMMU=\"NONE\""
  }
  aes_secworks {
    set TOP aes
    set CLOCK_PORT clk
    set RTL_FILES [glob ${NEW_BENCH_ROOT}/aes_secworks/*.v]
    set ELAB_PARAMS ""
  }
  default {
    echo "Unsupported NEW_BENCH: ${BENCH}"
    exit 2
  }
}

set OUT_DIR ../new_bench_baseline/${BENCH}
set RESULTS_DIR ${OUT_DIR}/results
set REPORTS_DIR ${OUT_DIR}/reports
file mkdir ${RESULTS_DIR}
file mkdir ${REPORTS_DIR}

set_app_var search_path ". ${NEW_BENCH_ROOT}/${BENCH} ${std_library_path} ${io_library_path} $search_path"
set_app_var target_library "saed32rvt_ss0p95v125c.db"
set_app_var link_library "* saed32rvt_ss0p95v125c.db dw_foundation.sldb"

define_design_lib NEW_BENCH_WORK -path ./NEW_BENCH_WORK_${BENCH}
analyze -format verilog ${RTL_FILES}

if {$ELAB_PARAMS ne ""} {
  elaborate ${TOP} -parameters ${ELAB_PARAMS}
} else {
  elaborate ${TOP}
}
current_design ${TOP}
link

# For mor1kx black-box stubs: mark stub modules as dont_touch so DC
# does not attempt to optimize their (empty) internals
if {$BENCH eq "mor1kx"} {
  foreach bb_cell {mor1kx_simple_dpram_sclk mor1kx_true_dpram_sclk} {
    if {[sizeof_collection [get_cells -hierarchical -quiet -filter "ref_name=~${bb_cell}*"]] > 0} {
      set_dont_touch [get_cells -hierarchical -quiet -filter "ref_name=~${bb_cell}*"]
    }
  }
}

set CLK_PERIOD 10.0
create_clock -period ${CLK_PERIOD} -name BENCH_CLK [get_ports ${CLOCK_PORT}]
set_clock_uncertainty -setup [expr $CLK_PERIOD * 0.1] [get_clocks BENCH_CLK]
set_clock_transition 0.08 [get_clocks BENCH_CLK]
set_ideal_network [get_ports ${CLOCK_PORT}]

set data_inputs [remove_from_collection [all_inputs] [get_ports ${CLOCK_PORT}]]
set_input_delay  -max [expr $CLK_PERIOD * 0.467] -clock BENCH_CLK ${data_inputs}
set_input_delay  -min [expr $CLK_PERIOD * 0.333] -clock BENCH_CLK ${data_inputs}
set_output_delay -max [expr $CLK_PERIOD * 0.467] -clock BENCH_CLK [all_outputs]
set_output_delay -min [expr $CLK_PERIOD * 0.333] -clock BENCH_CLK [all_outputs]
set_driving_cell -lib_cell INVX1_RVT -library saed32rvt_ss0p95v125c ${data_inputs}
set_load [load_of saed32rvt_ss0p95v125c/INVX4_RVT/A] [all_outputs]
set_max_fanout 16 [current_design]
set_max_transition 0.25 [current_design]
set_operating_conditions ss0p95v125c -library saed32rvt_ss0p95v125c

check_design > ${REPORTS_DIR}/pre_compile_check.rpt
compile_ultra
change_names -rules verilog -hierarchy

write -format ddc     -hierarchy -output ${RESULTS_DIR}/${BENCH}.mapped.ddc
write -format verilog -hierarchy -output ${RESULTS_DIR}/${BENCH}.mapped.v
write_sdc                                ${RESULTS_DIR}/${BENCH}.mapped.ss.sdc

report_qor                                            > ${REPORTS_DIR}/qor.rpt
report_area -hierarchy                                > ${REPORTS_DIR}/area.rpt
report_reference -hierarchy                           > ${REPORTS_DIR}/reference.rpt
report_constraint -all_violators -nosplit             > ${REPORTS_DIR}/constraints.rpt
report_timing -delay max -max_paths 20 -nosplit       > ${REPORTS_DIR}/setup.rpt
report_timing -delay min -max_paths 20 -nosplit       > ${REPORTS_DIR}/hold.rpt
check_design                                          > ${REPORTS_DIR}/post_compile_check.rpt

# ---------------------------------------------------------------
# Summary extraction: cell_area and seq_cells
# These are the two numbers needed for the overhead model.
# ---------------------------------------------------------------
set rpt_area [open ${REPORTS_DIR}/area_summary.rpt w]
set cell_area ""
if {[file exists ${REPORTS_DIR}/area.rpt]} {
  set fp [open ${REPORTS_DIR}/area.rpt r]
  while {[gets $fp line] >= 0} {
    if {[regexp {Total cell area:\s+([0-9\.]+)} $line match val]} {
      set cell_area $val
      break
    }
  }
  close $fp
}
set seq_count    [sizeof_collection [all_registers]]

# For mor1kx: also count how many black-box (stub) instances exist
# so the report reader can verify that memory FFs were excluded.
if {$BENCH eq "mor1kx"} {
  set bb_count 0
  foreach bb_cell {mor1kx_simple_dpram_sclk mor1kx_true_dpram_sclk} {
    set col [get_cells -hierarchical -quiet -filter "ref_name=~${bb_cell}*"]
    if {[sizeof_collection $col] > 0} {
      set bb_count [expr $bb_count + [sizeof_collection $col]]
    }
  }
  puts $rpt_area "benchmark,cell_area,seq_cells,blackbox_dpram_instances"
  puts $rpt_area "${BENCH},${cell_area},${seq_count},${bb_count}"
} else {
  puts $rpt_area "benchmark,cell_area,seq_cells"
  puts $rpt_area "${BENCH},${cell_area},${seq_count}"
}
close $rpt_area

echo "=== SYNTHESIS COMPLETE: ${BENCH} ==="
echo "cell_area  = ${cell_area}"
echo "seq_cells  = ${seq_count}"

exit
