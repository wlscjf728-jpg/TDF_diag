`timescale 1ns/1ps
module TB_step3_phase12;
  parameter L = 72;
  parameter NCHAINS = 5;
  localparam POS_W = (L <= 1) ? 1 : $clog2(L);

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

  integer i, errors;
  integer p1_cases, p1_correct, p1_vector_errors, p1_position_errors;
  integer p2_cases, p2_correct, p2_vector_errors, p2_position_errors;
  integer overflow_events;
  reg control_violation, x_seen;
  reg [L-1:0] seen_positions;

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
  always @(posedge clk_spare)
    if (rst_n && tdf_valid && (tdf_pos >= L)) overflow_events = overflow_events + 1;

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
    output reg [L-1:0] pattern;
    integer p;
    begin
      for (p = 0; p < L; p = p + 1) pattern[p] = p[0];
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

  task capture_reference;
    begin
      @(negedge clk_scan); oe = 1'b1; ce_scan = 1'b1;
      @(posedge clk_scan); #1; ce_scan = 1'b0; oe = 1'b0; #1;
    end
  endtask

  task inject_evidence_and_retrieve;
    begin
      seen_positions = 0;
      inject_result = 1'b1; pulse_spare_clock(); inject_result = 1'b0; @(negedge clk_spare); #1;
      cnt_clr = 1'b1; @(posedge clk_spare); #1; cnt_clr = 1'b0;
      cnt_en = 1'b1; se_spare = 1'b1;
      for (i = 0; i < L; i = i + 1) begin
        pulse_spare_clock();
        if (tdf_valid && (tdf_pos < L)) seen_positions[tdf_pos] = 1'b1;
      end
      cnt_en = 1'b0; se_spare = 1'b0;
    end
  endtask

  task force_q;
    input integer target_id;
    input integer value;
    begin
      case (target_id)
        0: if (value) force DUT.g_col[0].u_col.g_sc[0].u_scan_ff.q = 1'b1;
           else force DUT.g_col[0].u_col.g_sc[0].u_scan_ff.q = 1'b0;
        1: if (value) force DUT.g_col[0].u_col.g_sc[3].u_scan_ff.q = 1'b1;
           else force DUT.g_col[0].u_col.g_sc[3].u_scan_ff.q = 1'b0;
        2: if (value) force DUT.g_col[35].u_col.g_sc[1].u_scan_ff.q = 1'b1;
           else force DUT.g_col[35].u_col.g_sc[1].u_scan_ff.q = 1'b0;
        3: if (value) force DUT.g_col[35].u_col.g_sc[4].u_scan_ff.q = 1'b1;
           else force DUT.g_col[35].u_col.g_sc[4].u_scan_ff.q = 1'b0;
        4: if (value) force DUT.g_col[71].u_col.g_sc[2].u_scan_ff.q = 1'b1;
           else force DUT.g_col[71].u_col.g_sc[2].u_scan_ff.q = 1'b0;
      endcase
    end
  endtask

  task release_q;
    input integer target_id;
    begin
      case (target_id)
        0: release DUT.g_col[0].u_col.g_sc[0].u_scan_ff.q;
        1: release DUT.g_col[0].u_col.g_sc[3].u_scan_ff.q;
        2: release DUT.g_col[35].u_col.g_sc[1].u_scan_ff.q;
        3: release DUT.g_col[35].u_col.g_sc[4].u_scan_ff.q;
        4: release DUT.g_col[71].u_col.g_sc[2].u_scan_ff.q;
      endcase
    end
  endtask

  task force_d;
    input integer target_id;
    input integer value;
    begin
      case (target_id)
        0: if (value) force DUT.g_col[0].u_col.g_sc[0].scan_d = 1'b1;
           else force DUT.g_col[0].u_col.g_sc[0].scan_d = 1'b0;
        1: if (value) force DUT.g_col[0].u_col.g_sc[3].scan_d = 1'b1;
           else force DUT.g_col[0].u_col.g_sc[3].scan_d = 1'b0;
        2: if (value) force DUT.g_col[35].u_col.g_sc[1].scan_d = 1'b1;
           else force DUT.g_col[35].u_col.g_sc[1].scan_d = 1'b0;
        3: if (value) force DUT.g_col[35].u_col.g_sc[4].scan_d = 1'b1;
           else force DUT.g_col[35].u_col.g_sc[4].scan_d = 1'b0;
        4: if (value) force DUT.g_col[71].u_col.g_sc[2].scan_d = 1'b1;
           else force DUT.g_col[71].u_col.g_sc[2].scan_d = 1'b0;
      endcase
    end
  endtask

  task release_d;
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

  task check_phase1;
    input [NCHAINS*L-1:0] expected_vector;
    input [L-1:0] expected_positions;
    reg vector_ok;
    begin
      p1_cases = p1_cases + 1;
      #1;
      vector_ok = (b_vec === expected_vector);
      if (!vector_ok) begin p1_vector_errors = p1_vector_errors + 1; errors = errors + 1; end
      inject_evidence_and_retrieve();
      if (seen_positions !== expected_positions) begin p1_position_errors = p1_position_errors + 1; errors = errors + 1; end
      if (vector_ok && (seen_positions === expected_positions)) p1_correct = p1_correct + 1;
    end
  endtask

  task check_phase2;
    input [NCHAINS*L-1:0] expected_vector;
    input [L-1:0] expected_positions;
    reg vector_ok;
    begin
      p2_cases = p2_cases + 1;
      vector_ok = (b_vec === expected_vector);
      if (!vector_ok) begin p2_vector_errors = p2_vector_errors + 1; errors = errors + 1; end
      inject_evidence_and_retrieve();
      if (seen_positions !== expected_positions) begin p2_position_errors = p2_position_errors + 1; errors = errors + 1; end
      if (vector_ok && (seen_positions === expected_positions)) p2_correct = p2_correct + 1;
    end
  endtask

  initial begin : run_all
    reg [L-1:0] pattern, expected_positions;
    reg [NCHAINS*L-1:0] expected_vector;
    errors = 0; p1_cases = 0; p1_correct = 0; p1_vector_errors = 0; p1_position_errors = 0;
    p2_cases = 0; p2_correct = 0; p2_vector_errors = 0; p2_position_errors = 0;
    overflow_events = 0; control_violation = 1'b0; x_seen = 1'b0;
    build_pattern(pattern);

    // Phase 1: simultaneous permanent fault effects.
    reset_dut(); load_reference(pattern); capture_reference();
    force_q(0, 1); force_q(3, 0);
    expected_vector = 0; expected_vector[0] = 1; expected_vector[35*NCHAINS+4] = 1;
    expected_positions = 0; expected_positions[0] = 1; expected_positions[35] = 1;
    check_phase1(expected_vector, expected_positions); release_q(0); release_q(3);

    reset_dut(); load_reference(pattern); capture_reference();
    force_q(2, 0); force_q(3, 0);
    expected_vector = 0; expected_vector[35*NCHAINS+1] = 1; expected_vector[35*NCHAINS+4] = 1;
    expected_positions = 0; expected_positions[35] = 1;
    check_phase1(expected_vector, expected_positions); release_q(2); release_q(3);

    reset_dut(); load_reference(pattern); capture_reference();
    force_q(1, 1); force_q(2, 0); force_q(4, 0);
    expected_vector = 0; expected_vector[3] = 1; expected_vector[35*NCHAINS+1] = 1; expected_vector[71*NCHAINS+2] = 1;
    expected_positions = 0; expected_positions[0] = 1; expected_positions[35] = 1; expected_positions[71] = 1;
    check_phase1(expected_vector, expected_positions); release_q(1); release_q(2); release_q(4);

    reset_dut(); load_reference(pattern); capture_reference();
    force_q(0, 1); force_q(4, 0); mask[0] = 1'b1;
    expected_vector = 0; expected_vector[71*NCHAINS+2] = 1;
    expected_positions = 0; expected_positions[71] = 1;
    check_phase1(expected_vector, expected_positions); release_q(0); release_q(4);

    $display("STEP3_PHASE1_SUMMARY cases=%0d correct=%0d vector_errors=%0d position_errors=%0d",
      p1_cases, p1_correct, p1_vector_errors, p1_position_errors);
    if ((p1_cases == p1_correct) && (p1_vector_errors == 0) && (p1_position_errors == 0))
      $display("PASS: Step 3 Phase 1 multiple permanent faults");
    else $display("FAIL: Step 3 Phase 1 multiple permanent faults");

    // Phase 2: simultaneous transition-delay effects around the 5 ns capture margin.
    reset_dut(); load_reference(pattern);
    @(negedge clk_scan); oe = 1'b1; ce_scan = 1'b1; force_d(0, 1); force_d(3, 0);
    fork begin #6; release_d(0); release_d(3); end join_none
    @(posedge clk_scan); #1; ce_scan = 1'b0; oe = 1'b0; #10;
    expected_vector = 0; expected_vector[0] = 1; expected_vector[35*NCHAINS+4] = 1;
    expected_positions = 0; expected_positions[0] = 1; expected_positions[35] = 1;
    check_phase2(expected_vector, expected_positions);

    reset_dut(); load_reference(pattern);
    @(negedge clk_scan); oe = 1'b1; ce_scan = 1'b1; force_d(1, 1); force_d(4, 0);
    fork begin #4; release_d(1); end begin #6; release_d(4); end join_none
    @(posedge clk_scan); #1; ce_scan = 1'b0; oe = 1'b0; #10;
    expected_vector = 0; expected_vector[71*NCHAINS+2] = 1;
    expected_positions = 0; expected_positions[71] = 1;
    check_phase2(expected_vector, expected_positions);

    reset_dut(); load_reference(pattern);
    @(negedge clk_scan); oe = 1'b1; ce_scan = 1'b1; force_d(2, 0); force_d(3, 0);
    fork begin #6; release_d(2); release_d(3); end join_none
    @(posedge clk_scan); #1; ce_scan = 1'b0; oe = 1'b0; #10;
    expected_vector = 0; expected_vector[35*NCHAINS+1] = 1; expected_vector[35*NCHAINS+4] = 1;
    expected_positions = 0; expected_positions[35] = 1;
    check_phase2(expected_vector, expected_positions);

    reset_dut(); load_reference(pattern);
    @(negedge clk_scan); oe = 1'b1; ce_scan = 1'b1; force_d(0, 1); force_d(4, 0);
    fork begin #4; release_d(0); release_d(4); end join_none
    @(posedge clk_scan); #1; ce_scan = 1'b0; oe = 1'b0; #10;
    expected_vector = 0; expected_positions = 0;
    check_phase2(expected_vector, expected_positions);

    $display("STEP3_PHASE2_SUMMARY cases=%0d correct=%0d vector_errors=%0d position_errors=%0d",
      p2_cases, p2_correct, p2_vector_errors, p2_position_errors);
    if ((p2_cases == p2_correct) && (p2_vector_errors == 0) && (p2_position_errors == 0))
      $display("PASS: Step 3 Phase 2 multiple transition-delay effects");
    else $display("FAIL: Step 3 Phase 2 multiple transition-delay effects");

    if (overflow_events != 0) begin errors = errors + 1; $display("FAIL: tdf_pos overflow count %0d", overflow_events); end
    if (control_violation) begin errors = errors + 1; $display("FAIL: scan/spare enables overlapped"); end
    if (x_seen) begin errors = errors + 1; $display("FAIL: X observed on mismatch vector"); end
    if (errors == 0) $display("PASS: Step 3 Phase 1-2 combined regression");
    else $display("FAIL: Step 3 Phase 1-2 combined regression with %0d errors", errors);
    $finish;
  end
endmodule
