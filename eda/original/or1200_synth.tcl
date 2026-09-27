source ../../common_setup.tcl

set BENCH    or1200
set TOP      or1200_system
set RTL_ORIG "/srscl/home/jcjeong/LBIST_inf/dc/rtl/BenchMark/OR1200"
set RTL_NEW  "${PJT_PATH}/RTL/or1200"
set OUT_DIR  "../new_bench_baseline/${BENCH}"
set RESULTS_DIR "${OUT_DIR}/results"
set REPORTS_DIR "${OUT_DIR}/reports"
file mkdir ${RESULTS_DIR}
file mkdir ${REPORTS_DIR}

set_app_var search_path ". ${RTL_ORIG} ${RTL_NEW} ${std_library_path} ${io_library_path} ${RAM_path}/db_nldm $search_path"
set_app_var target_library "saed32rvt_ss0p95v125c.db"
set_app_var link_library   "* saed32rvt_ss0p95v125c.db ${RAM_path}/db_nldm/saed32sram_ss0p95v125c.db dw_foundation.sldb"

define_design_lib OR1200_WORK -path ./OR1200_WORK

analyze -format sverilog [list ${RTL_NEW}/or1200_mem_stub.v ${RTL_NEW}/or1200_system.v]

set SRAM_EXCLUDE {
    or1200_spram.v or1200_spram_32_bw.v
    or1200_spram_32x24.v or1200_spram_64x14.v or1200_spram_64x22.v or1200_spram_64x24.v
    or1200_spram_128x32.v or1200_spram_256x21.v or1200_spram_512x20.v
    or1200_spram_1024x8.v or1200_spram_1024x32.v or1200_spram_1024x32_bw.v
    or1200_spram_2048x8.v or1200_spram_2048x32.v or1200_spram_2048x32_bw.v
    or1200_dpram.v or1200_dpram_32x32.v or1200_dpram_256x32.v
    or1200_rfram_generic.v or1200_tpram_32x32.v
    or1200_xcv_ram32x8d.v memory_bb.v
}

set RTL_FILES [list]
foreach f [lsort [glob ${RTL_ORIG}/*.v]] {
    if {[lsearch -exact $SRAM_EXCLUDE [file tail $f]] < 0} {
        lappend RTL_FILES $f
    }
}

analyze -format verilog $RTL_FILES
elaborate ${TOP}
current_design ${TOP}
link

set CLK_PERIOD 10.0
create_clock -period ${CLK_PERIOD} -name BENCH_CLK [get_ports clk_i]
set_clock_uncertainty -setup [expr $CLK_PERIOD * 0.1] [get_clocks BENCH_CLK]
set_clock_transition 0.08 [get_clocks BENCH_CLK]
set_ideal_network [get_ports clk_i]

set data_inputs [remove_from_collection [all_inputs] [get_ports clk_i]]
if {[sizeof_collection $data_inputs] > 0} {
    set_input_delay -max [expr $CLK_PERIOD * 0.467] -clock BENCH_CLK $data_inputs
    set_input_delay -min [expr $CLK_PERIOD * 0.333] -clock BENCH_CLK $data_inputs
    set_driving_cell -lib_cell INVX1_RVT -library saed32rvt_ss0p95v125c $data_inputs
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

report_qor                                      > ${REPORTS_DIR}/qor.rpt
report_area -hierarchy                          > ${REPORTS_DIR}/area.rpt
report_reference -hierarchy                     > ${REPORTS_DIR}/reference.rpt
report_constraint -all_violators -nosplit       > ${REPORTS_DIR}/constraints.rpt
report_timing -delay max -max_paths 20 -nosplit > ${REPORTS_DIR}/setup.rpt
report_timing -delay min -max_paths 20 -nosplit > ${REPORTS_DIR}/hold.rpt
check_design                                    > ${REPORTS_DIR}/post_compile_check.rpt

set rpt [open ${REPORTS_DIR}/area_summary.rpt w]
set cell_area ""
set fp [open ${REPORTS_DIR}/area.rpt r]
while {[gets $fp line] >= 0} {
    if {[regexp {Total cell area:\s+([0-9.]+)} $line match val]} {
        set cell_area $val
        break
    }
}
close $fp
set seq_count  [sizeof_collection [all_registers]]
set sram_count [sizeof_collection [get_cells -hierarchical -quiet -filter "ref_name=~SRAM1RW512x32"]]
puts $rpt "benchmark,cell_area,seq_cells,sram1rw512x32_instances"
puts $rpt "${BENCH},${cell_area},${seq_count},${sram_count}"
close $rpt

echo "=== SYNTHESIS COMPLETE: ${BENCH} ==="
echo "cell_area  = ${cell_area}"
echo "seq_cells  = ${seq_count}"
echo "SRAM macro = ${sram_count} x SRAM1RW512x32"

exit
