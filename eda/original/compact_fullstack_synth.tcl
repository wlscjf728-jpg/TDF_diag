source ../../common_setup.tcl

if {![info exists ::env(COMPACT_MODE)]} {
  echo "COMPACT_MODE must be scan_only, conventional, or proposed"
  exit 2
}
set MODE $::env(COMPACT_MODE)
set L 72
set N_TOTAL 160
set NSP 1
if {[info exists ::env(COMPACT_L)]} { set L $::env(COMPACT_L) }
if {[info exists ::env(COMPACT_NTOTAL)]} { set N_TOTAL $::env(COMPACT_NTOTAL) }
if {[info exists ::env(COMPACT_NSP)]} { set NSP $::env(COMPACT_NSP) }

if {$MODE == "scan_only"} {
  set TOP step2_scan_baseline
  set PARAMS "L=${L},N_TOTAL=${N_TOTAL}"
  set LABEL scan_only_L${L}_N${N_TOTAL}
} elseif {$MODE == "conventional"} {
  set TOP compact_production_top
  set PARAMS "L=${L},N_TOTAL=${N_TOTAL},NSP=1"
  set LABEL conventional_nsp1_L${L}_N${N_TOTAL}
} elseif {$MODE == "proposed"} {
  set TOP compact_production_top
  set PARAMS "L=${L},N_TOTAL=${N_TOTAL},NSP=${NSP}"
  set LABEL proposed_nsp${NSP}_L${L}_N${N_TOTAL}
} else {
  echo "Unsupported COMPACT_MODE: ${MODE}"
  exit 2
}

set OUT_DIR ../compact_fullstack/${LABEL}
set RESULTS_DIR ${OUT_DIR}/results
set REPORTS_DIR ${OUT_DIR}/reports
file mkdir ${RESULTS_DIR}
file mkdir ${REPORTS_DIR}

set_app_var search_path ". ${std_library_path} ${io_library_path} $search_path"
set_app_var target_library "saed32rvt_ss0p95v125c.db"
set_app_var link_library "* saed32rvt_ss0p95v125c.db dw_foundation.sldb"

define_design_lib COMPACT_WORK -path ./COMPACT_WORK_${LABEL}
analyze -format verilog [list \
  ${dc_source_path}/top_module.v \
  ${dc_source_path}/step2_nsp_top.v \
  ${dc_source_path}/compact_production_top.v \
]
elaborate ${TOP} -parameters ${PARAMS}
current_design [get_object_name [current_design]]
link

set CLK_PERIOD 10.0
create_clock -period ${CLK_PERIOD} -name CLK_SCAN [get_ports clk_scan]
set_clock_uncertainty -setup [expr $CLK_PERIOD * 0.1] [get_clocks CLK_SCAN]
set_clock_transition 0.08 [get_clocks CLK_SCAN]
set_ideal_network [get_ports clk_scan]

if {$MODE != "scan_only"} {
  create_clock -period [expr $CLK_PERIOD * 2.0] -name CLK_SPARE [get_ports clk_spare]
  set_clock_uncertainty -setup [expr $CLK_PERIOD * 0.1] [get_clocks CLK_SPARE]
  set_clock_transition 0.08 [get_clocks CLK_SPARE]
  set_ideal_network [get_ports clk_spare]
}

set clock_ports [get_ports clk_scan]
if {$MODE != "scan_only"} {
  set clock_ports [add_to_collection $clock_ports [get_ports clk_spare]]
}
set data_inputs [remove_from_collection [all_inputs] $clock_ports]
set_input_delay -max [expr $CLK_PERIOD * 0.467] -clock CLK_SCAN $data_inputs
set_input_delay -min [expr $CLK_PERIOD * 0.333] -clock CLK_SCAN $data_inputs
set_output_delay -max [expr $CLK_PERIOD * 0.467] -clock CLK_SCAN [all_outputs]
set_output_delay -min [expr $CLK_PERIOD * 0.333] -clock CLK_SCAN [all_outputs]
set_driving_cell -lib_cell INVX1_RVT -library saed32rvt_ss0p95v125c $data_inputs
set_load [load_of saed32rvt_ss0p95v125c/INVX4_RVT/A] [all_outputs]
set_max_fanout 16 [current_design]
set_max_transition 0.25 [current_design]
set_operating_conditions ss0p95v125c -library saed32rvt_ss0p95v125c

check_design > ${REPORTS_DIR}/pre_compile_check.rpt
compile_ultra -area_high_effort_script
change_names -rules verilog -hierarchy

write -format verilog -hierarchy -output ${RESULTS_DIR}/${LABEL}.mapped.v
write -format ddc -hierarchy -output ${RESULTS_DIR}/${LABEL}.mapped.ddc
write_sdc ${RESULTS_DIR}/${LABEL}.mapped.ss.sdc

report_qor > ${REPORTS_DIR}/qor.rpt
report_area -hierarchy > ${REPORTS_DIR}/area.rpt
report_reference -hierarchy > ${REPORTS_DIR}/reference.rpt
report_constraint -all_violators -nosplit > ${REPORTS_DIR}/constraints.rpt
report_timing -delay max -max_paths 20 -nosplit > ${REPORTS_DIR}/setup.rpt
report_timing -delay min -max_paths 20 -nosplit > ${REPORTS_DIR}/hold.rpt
check_design > ${REPORTS_DIR}/post_compile_check.rpt

exit
