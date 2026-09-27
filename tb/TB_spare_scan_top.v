`timescale 1ns/1ps
module TB_spare_scan_top;
  parameter L = 72;
  parameter NCHAINS = 5;
  localparam POS_W = (L <= 1) ? 1 : $clog2(L);
  localparam CAPTURE_MARGIN_NS = 5;

  reg clk_scan, clk_spare, rst_n;
  reg se_scan, se_spare, ce_scan, ce_spare, oe;
  reg cnt_en, cnt_clr, spare_si, inject_result;
  reg [NCHAINS-1:0] scan_si;
  wire [NCHAINS-1:0] scan_so;
  wire spare_so;
  reg [NCHAINS*L-1:0] mask;
  wire [NCHAINS*L-1:0] b_vec;
  wire [POS_W-1:0] tdf_pos;
  wire tdf_valid;

  integer i, errors, total_cases, expected_detects, correct_detects;
  integer false_positives, false_negatives, wrong_locations, wrong_vectors;
  integer no_fault_failures, overflow_events;
  reg [NCHAINS-1:0] chain_coverage;
  reg [2:0] column_region_coverage;
  reg control_violation, x_seen, injection_hold_value;
  reg saw_expected_position, saw_unexpected_position, saw_shift_one;

  spare_scan_top #(.L(L), .NCHAINS(NCHAINS)) DUT (
    .clk_scan(clk_scan), .clk_spare(clk_spare), .rst_n(rst_n),
    .se_scan(se_scan), .se_spare(se_spare), .ce_scan(ce_scan), .ce_spare(ce_spare),
    .oe(oe), .cnt_en(cnt_en), .cnt_clr(cnt_clr),
    .scan_si(scan_si), .scan_so(scan_so), .spare_si(spare_si), .spare_so(spare_so),
    .mask(mask), .b_vec(b_vec), .inject_result(inject_result),
    .tdf_pos(tdf_pos), .tdf_valid(tdf_valid)
  );

  initial begin clk_scan = 1'b0; forever #5 clk_scan = ~clk_scan; end
  initial begin clk_spare = 1'b0; forever #10 clk_spare = ~clk_spare; end

  always @(*) begin
    if (rst_n && ce_scan && ce_spare) control_violation = 1'b1;
    if (rst_n && ((^b_vec) === 1'bx)) x_seen = 1'b1;
  end
  always @(posedge clk_spare) if (rst_n && tdf_valid && (tdf_pos >= L)) overflow_events = overflow_events + 1;

  task force_target;
    input integer target_id;
    begin
      case (target_id)
        0: force DUT.g_col[0].u_col.g_sc[0].scan_d = injection_hold_value;
        1: force DUT.g_col[0].u_col.g_sc[3].scan_d = injection_hold_value;
        2: force DUT.g_col[35].u_col.g_sc[1].scan_d = injection_hold_value;
        3: force DUT.g_col[35].u_col.g_sc[4].scan_d = injection_hold_value;
        4: force DUT.g_col[71].u_col.g_sc[2].scan_d = injection_hold_value;
      endcase
    end
  endtask

  task release_target;
    input integer target_id;
    begin
      case (target_id)
        0: release DUT.g_col[0].u_col.g_sc[0].scan_d;
        1: release DUT.g_col[0].u_col.g_sc[3].scan_d;
        2: release DUT.g_col[35].u_col.g_sc[1].scan_d;
        3: release DUT.g_col[35].u_col.g_sc[4].scan_d;
        4: release DUT.g_col[71].u_col.g_sc[2].scan_d;
      endcase
    end
  endtask

  task pulse_spare_clock;
    begin ce_spare = 1'b1; @(posedge clk_spare); #1; ce_spare = 1'b0; end
  endtask

  task reset_dut;
    begin
      rst_n = 1'b0; se_scan = 1'b0; se_spare = 1'b0; ce_scan = 1'b0; ce_spare = 1'b0;
      oe = 1'b0; cnt_en = 1'b0; cnt_clr = 1'b0; scan_si = 0; spare_si = 1'b0;
      mask = 0; inject_result = 1'b0; #25; rst_n = 1'b1; #1;
    end
  endtask

  task build_pattern;
    input integer target_col;
    input integer target_value;
    output reg [L-1:0] pattern;
    integer p;
    begin
      for (p = 0; p < L; p = p + 1)
        pattern[p] = ((p % 2) == (target_col % 2)) ? target_value : !target_value;
    end
  endtask

  task load_reference;
    input [L-1:0] pattern;
    begin
      se_spare = 1'b1;
      for (i = L-1; i >= 0; i = i - 1) begin spare_si = pattern[i]; pulse_spare_clock(); end
      se_spare = 1'b0; spare_si = 1'b0; @(negedge clk_spare); #1;
    end
  endtask

  task retrieve_evidence;
    input integer expected_col;
    begin
      saw_expected_position = 1'b0; saw_unexpected_position = 1'b0; saw_shift_one = 1'b0;
      inject_result = 1'b1; pulse_spare_clock(); inject_result = 1'b0; @(negedge clk_spare); #1;
      cnt_clr = 1'b1; @(posedge clk_spare); #1; cnt_clr = 1'b0;
      cnt_en = 1'b1; se_spare = 1'b1;
      for (i = 0; i < L; i = i + 1) begin
        pulse_spare_clock();
        if (spare_so) saw_shift_one = 1'b1;
        if (tdf_valid && (tdf_pos == expected_col)) saw_expected_position = 1'b1;
        if (tdf_valid && (tdf_pos != expected_col)) saw_unexpected_position = 1'b1;
      end
      cnt_en = 1'b0; se_spare = 1'b0;
    end
  endtask

  task run_no_fault_control;
    input integer phase;
    reg [L-1:0] pattern;
    begin
      build_pattern(0, phase, pattern);
      reset_dut(); load_reference(pattern);
      @(negedge clk_scan); oe = 1'b1; ce_scan = 1'b1; @(posedge clk_scan); #1; ce_scan = 1'b0; oe = 1'b0; #1;
      if (b_vec !== 0) begin no_fault_failures = no_fault_failures + 1; errors = errors + 1; end
      retrieve_evidence(0);
      if (saw_expected_position || saw_unexpected_position || saw_shift_one) begin
        no_fault_failures = no_fault_failures + 1; errors = errors + 1;
      end
    end
  endtask

  task run_case;
    input integer target_id;
    input integer target_col;
    input integer target_chain;
    input integer direction; // 0 rise, 1 fall
    input integer delay_ns;
    reg [L-1:0] pattern;
    reg [NCHAINS*L-1:0] expected_vector;
    integer expect_detection;
    integer target_bit;
    begin
      expect_detection = (delay_ns > CAPTURE_MARGIN_NS);
      target_bit = (target_col * NCHAINS) + target_chain;
      build_pattern(target_col, direction ? 0 : 1, pattern);
      expected_vector = 0; expected_vector[target_bit] = 1'b1;
      injection_hold_value = direction ? 1'b1 : 1'b0;
      total_cases = total_cases + 1;
      if (expect_detection) expected_detects = expected_detects + 1;

      reset_dut(); load_reference(pattern);
      @(negedge clk_scan); oe = 1'b1; ce_scan = 1'b1; force_target(target_id);
      fork begin #(delay_ns); release_target(target_id); end join_none
      @(posedge clk_scan); #1; ce_scan = 1'b0; oe = 1'b0; #10;

      if (expect_detection && (b_vec !== expected_vector)) begin wrong_vectors = wrong_vectors + 1; errors = errors + 1; end
      if (!expect_detection && (b_vec !== 0)) begin false_positives = false_positives + 1; errors = errors + 1; end
      retrieve_evidence(target_col);
      if (expect_detection) begin
        if (saw_expected_position && !saw_unexpected_position && saw_shift_one) begin
          correct_detects = correct_detects + 1; chain_coverage[target_chain] = 1'b1;
          if (target_col == 0) column_region_coverage[0] = 1'b1;
          if (target_col == 35) column_region_coverage[1] = 1'b1;
          if (target_col == 71) column_region_coverage[2] = 1'b1;
        end else begin
          if (!saw_expected_position || !saw_shift_one) false_negatives = false_negatives + 1;
          if (saw_unexpected_position) wrong_locations = wrong_locations + 1;
          errors = errors + 1;
        end
      end else if (saw_expected_position || saw_unexpected_position || saw_shift_one) begin
        false_positives = false_positives + 1; errors = errors + 1;
      end
    end
  endtask

  task run_target_suite;
    input integer target_id;
    input integer target_col;
    input integer target_chain;
    begin
      run_case(target_id, target_col, target_chain, 0, 4);
      run_case(target_id, target_col, target_chain, 0, 6);
      run_case(target_id, target_col, target_chain, 1, 4);
      run_case(target_id, target_col, target_chain, 1, 6);
    end
  endtask

  initial begin
    errors = 0; total_cases = 0; expected_detects = 0; correct_detects = 0;
    false_positives = 0; false_negatives = 0; wrong_locations = 0; wrong_vectors = 0;
    no_fault_failures = 0; overflow_events = 0; chain_coverage = 0; column_region_coverage = 0;
    control_violation = 1'b0; x_seen = 1'b0;

    run_no_fault_control(0); run_no_fault_control(1);
    run_target_suite(0, 0, 0);
    run_target_suite(1, 0, 3);
    run_target_suite(2, 35, 1);
    run_target_suite(3, 35, 4);
    run_target_suite(4, 71, 2);

    if (chain_coverage !== {NCHAINS{1'b1}}) begin errors = errors + 1; $display("FAIL: chain coverage %b", chain_coverage); end
    if (column_region_coverage !== 3'b111) begin errors = errors + 1; $display("FAIL: column region coverage %b", column_region_coverage); end
    if (overflow_events != 0) begin errors = errors + 1; $display("FAIL: tdf_pos overflow count %0d", overflow_events); end
    if (control_violation) begin errors = errors + 1; $display("FAIL: scan/spare enables overlapped"); end
    if (x_seen) begin errors = errors + 1; $display("FAIL: X observed on mismatch vector"); end

    $display("PHASE4_SUMMARY L=%0d NCHAINS=%0d total=%0d expected_detect=%0d correct=%0d fp=%0d fn=%0d wrong_location=%0d wrong_vector=%0d no_fault_fail=%0d overflow=%0d chain_coverage=%b regions=%b",
      L, NCHAINS, total_cases, expected_detects, correct_detects, false_positives, false_negatives,
      wrong_locations, wrong_vectors, no_fault_failures, overflow_events, chain_coverage, column_region_coverage);
    if (errors == 0) $display("PASS: Phase 4 72x5 representative regression");
    else $display("FAIL: Phase 4 regression failed with %0d errors", errors);
    $finish;
  end
endmodule
