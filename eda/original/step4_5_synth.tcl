source ../../common_setup.tcl

set TOP $::env(STEP4_5_TOP)
set CORNER $::env(STEP4_5_CORNER)
set LABEL "${TOP}_${CORNER}"

if {$CORNER == "SS"} {
  set LIB_DB saed32rvt_ss0p95v125c.db
  set LIB saed32rvt_ss0p95v125c
  set OC ss0p95v125c
} elseif {$CORNER == "FF"} {
  set LIB_DB saed32rvt_ff1p16v125c.db
  set LIB saed32rvt_ff1p16v125c
  set OC ff1p16v125c
} else {
  echo "STEP4_5_CORNER must be SS or FF"
  exit 2
}

set OUT_DIR ../step4_5/${LABEL}
set RESULTS_DIR ${OUT_DIR}/results
set REPORTS_DIR ${OUT_DIR}/reports
file mkdir ${RESULTS_DIR}
file mkdir ${REPORTS_DIR}

set_app_var search_path ". ${std_library_path} $search_path"
set_app_var target_library $LIB_DB
set_app_var link_library "* $LIB_DB dw_foundation.sldb"

define_design_lib STEP4_5_WORK -path ./STEP4_5_WORK_${LABEL}
analyze -format verilog ${dc_source_path}/step4_5_lockup_compare.v
elaborate ${TOP}
current_design ${TOP}
link

if {$TOP == "step4_5_scan_ff_only" || $TOP == "step4_5_scan_mux_ff"} {
  create_clock -period 10.0 -waveform {0 5} -name CLK_SCAN [get_ports clk_scan]
  set clk_port [get_ports clk_scan]
  set clk_obj [get_clocks CLK_SCAN]
} else {
  create_clock -period 20.0 -waveform {0 10} -name CLK_SPARE [get_ports clk_spare]
  set clk_port [get_ports clk_spare]
  set clk_obj [get_clocks CLK_SPARE]
}
set_clock_uncertainty -setup 1.0 $clk_obj
set_clock_transition 0.08 $clk_obj
set_ideal_network $clk_port

set data_inputs [remove_from_collection [all_inputs] $clk_port]
set_input_delay -max 4.67 -clock $clk_obj $data_inputs
set_input_delay -min 3.33 -clock $clk_obj $data_inputs
set_output_delay -max 4.67 -clock $clk_obj [all_outputs]
set_output_delay -min 3.33 -clock $clk_obj [all_outputs]
set_driving_cell -lib_cell INVX1_RVT -library $LIB $data_inputs
set_load [load_of ${LIB}/INVX4_RVT/A] [all_outputs]
set_max_fanout 16 [current_design]
set_max_transition 0.25 [current_design]
set_operating_conditions $OC -library $LIB

if {$TOP == "step4_5_spare_forced_lockup"} {
  set_dont_touch [get_cells -hierarchical *u_lockup*]
}

check_design > ${REPORTS_DIR}/pre_compile_check.rpt
compile_ultra
change_names -rules verilog -hierarchy

write -format verilog -hierarchy -output ${RESULTS_DIR}/${TOP}.mapped.v
write -format ddc -hierarchy -output ${RESULTS_DIR}/${TOP}.mapped.ddc
write_sdc ${RESULTS_DIR}/${TOP}.mapped.sdc
report_qor > ${REPORTS_DIR}/qor.rpt
report_area -hierarchy > ${REPORTS_DIR}/area.rpt
report_reference -hierarchy > ${REPORTS_DIR}/reference.rpt
report_constraint -all_violators -nosplit > ${REPORTS_DIR}/constraints.rpt
check_design > ${REPORTS_DIR}/post_compile_check.rpt
exit
