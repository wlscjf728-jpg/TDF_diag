source ../../common_setup.tcl

set BENCH openmsp430
set TOP omsp_with_sram_wrapper
set CLOCK_PORT clk
set RTL_ROOT "${PJT_PATH}/RTL/openmsp430"
set OUT_DIR ../new_bench_baseline/${BENCH}
set RESULTS_DIR ${OUT_DIR}/results
set REPORTS_DIR ${OUT_DIR}/reports

file mkdir ${RESULTS_DIR}
file mkdir ${REPORTS_DIR}

set_app_var search_path ". ${RTL_ROOT} ${RTL_ROOT}/periph ${std_library_path} ${io_library_path} ${PDK}/lib/sram/db_nldm $search_path"
set_app_var target_library "saed32rvt_ss0p95v125c.db"
set_app_var link_library "* saed32rvt_ss0p95v125c.db saed32sram_ss0p95v125c.db dw_foundation.sldb"

set RTL_FILES [list ${RTL_ROOT}/omsp_with_sram_wrapper.v]
foreach f [concat [lsort [glob -nocomplain ${RTL_ROOT}/*.v]] [lsort [glob -nocomplain ${RTL_ROOT}/periph/*.v]]] {
  if {[string match "*omsp_with_sram_wrapper.v" [file tail $f]]} { continue }
  lappend RTL_FILES $f
}

define_design_lib OPENMSP430_WORK -path ./OPENMSP430_WORK
analyze -format verilog ${RTL_FILES}
elaborate ${TOP}
current_design ${TOP}
link

set CLK_PERIOD 10.0
create_clock -period ${CLK_PERIOD} -name BENCH_CLK [get_ports ${CLOCK_PORT}]
set_clock_uncertainty -setup [expr $CLK_PERIOD * 0.1] [get_clocks BENCH_CLK]
set_clock_transition 0.08 [get_clocks BENCH_CLK]
set_ideal_network [get_ports ${CLOCK_PORT}]

set data_inputs [remove_from_collection [all_inputs] [get_ports ${CLOCK_PORT}]]
if {[sizeof_collection ${data_inputs}] > 0} {
  set_input_delay -max [expr $CLK_PERIOD * 0.467] -clock BENCH_CLK ${data_inputs}
  set_input_delay -min [expr $CLK_PERIOD * 0.333] -clock BENCH_CLK ${data_inputs}
  set_driving_cell -lib_cell INVX1_RVT -library saed32rvt_ss0p95v125c ${data_inputs}
}
if {[sizeof_collection [all_outputs]] > 0} {
  set_output_delay -max [expr $CLK_PERIOD * 0.467] -clock BENCH_CLK [all_outputs]
  set_output_delay -min [expr $CLK_PERIOD * 0.333] -clock BENCH_CLK [all_outputs]
  set_load [load_of saed32rvt_ss0p95v125c/INVX4_RVT/A] [all_outputs]
}

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
set seq_count [sizeof_collection [all_registers]]
puts $rpt_area "benchmark,cell_area,seq_cells"
puts $rpt_area "${BENCH},${cell_area},${seq_count}"
close $rpt_area

echo "=== SYNTHESIS COMPLETE: ${BENCH} ==="
echo "cell_area  = ${cell_area}"
echo "seq_cells  = ${seq_count}"

exit
