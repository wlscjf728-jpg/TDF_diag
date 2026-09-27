`timescale 1ns/1ps
module TB_step3_phase34;
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

  integer i, subset_index, errors, overflow_events;
  integer p3_opportunities, p3_active_opportunities, p3_correct;
  integer p3_vector_errors, p3_position_errors;
  integer p4_cases, p4_fault_instances, p4_correct;
  integer p4_vector_errors, p4_position_errors;
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

  task load_reference;
    begin
      se_spare = 1'b1;
      for (i = L-1; i >= 0; i = i-1) begin spare_si = i[0]; pulse_spare_clock(); end
      se_spare = 1'b0; spare_si = 1'b0; @(negedge clk_spare); #1;
      @(negedge clk_scan); oe = 1'b1; ce_scan = 1'b1;
      @(posedge clk_scan); #1; ce_scan = 1'b0; oe = 1'b0; #1;
    end
  endtask

  task force_target;
    input integer id;
    begin
      case (id)
        0: force DUT.g_col[0].u_col.g_sc[0].u_scan_ff.q = 1'b1;
        1: force DUT.g_col[0].u_col.g_sc[3].u_scan_ff.q = 1'b1;
        2: force DUT.g_col[35].u_col.g_sc[1].u_scan_ff.q = 1'b0;
        3: force DUT.g_col[35].u_col.g_sc[4].u_scan_ff.q = 1'b0;
        4: force DUT.g_col[71].u_col.g_sc[2].u_scan_ff.q = 1'b0;
      endcase
    end
  endtask

  task release_target;
    input integer id;
    begin
      case (id)
        0: release DUT.g_col[0].u_col.g_sc[0].u_scan_ff.q;
        1: release DUT.g_col[0].u_col.g_sc[3].u_scan_ff.q;
        2: release DUT.g_col[35].u_col.g_sc[1].u_scan_ff.q;
        3: release DUT.g_col[35].u_col.g_sc[4].u_scan_ff.q;
        4: release DUT.g_col[71].u_col.g_sc[2].u_scan_ff.q;
      endcase
    end
  endtask

  task apply_set;
    input [4:0] active_set;
    integer j;
    begin
      for (j = 0; j < 5; j = j+1) if (active_set[j]) force_target(j);
      #1;
    end
  endtask

  task release_set;
    input [4:0] active_set;
    integer j;
    begin
      for (j = 0; j < 5; j = j+1) if (active_set[j]) release_target(j);
    end
  endtask

  task make_expected;
    input [4:0] active_set;
    output reg [NCHAINS*L-1:0] expected_vector;
    output reg [L-1:0] expected_positions;
    begin
      expected_vector = 0; expected_positions = 0;
      if (active_set[0]) begin expected_vector[0] = 1; expected_positions[0] = 1; end
      if (active_set[1]) begin expected_vector[3] = 1; expected_positions[0] = 1; end
      if (active_set[2]) begin expected_vector[35*NCHAINS+1] = 1; expected_positions[35] = 1; end
      if (active_set[3]) begin expected_vector[35*NCHAINS+4] = 1; expected_positions[35] = 1; end
      if (active_set[4]) begin expected_vector[71*NCHAINS+2] = 1; expected_positions[71] = 1; end
    end
  endtask

  task retrieve_evidence;
    begin
      seen_positions = 0;
      inject_result = 1'b1; pulse_spare_clock(); inject_result = 1'b0; @(negedge clk_spare); #1;
      cnt_clr = 1'b1; @(posedge clk_spare); #1; cnt_clr = 1'b0;
      cnt_en = 1'b1; se_spare = 1'b1;
      for (i = 0; i < L; i = i+1) begin
        pulse_spare_clock();
        if (tdf_valid && (tdf_pos < L)) seen_positions[tdf_pos] = 1'b1;
      end
      cnt_en = 1'b0; se_spare = 1'b0;
    end
  endtask

  task run_phase3_case;
    input [4:0] active_set;
    reg [NCHAINS*L-1:0] expected_vector;
    reg [L-1:0] expected_positions;
    reg vector_ok;
    begin
      p3_opportunities = p3_opportunities + 1;
      if (active_set != 0) p3_active_opportunities = p3_active_opportunities + 1;
      reset_dut(); load_reference(); apply_set(active_set);
      make_expected(active_set, expected_vector, expected_positions);
      vector_ok = (b_vec === expected_vector);
      if (!vector_ok) begin p3_vector_errors = p3_vector_errors + 1; errors = errors + 1; end
      retrieve_evidence();
      if (seen_positions !== expected_positions) begin p3_position_errors = p3_position_errors + 1; errors = errors + 1; end
      if (vector_ok && (seen_positions === expected_positions)) p3_correct = p3_correct + 1;
      release_set(active_set);
    end
  endtask

  task run_phase4_case;
    input [4:0] active_set;
    reg [NCHAINS*L-1:0] expected_vector;
    reg [L-1:0] expected_positions;
    reg vector_ok;
    integer j;
    begin
      p4_cases = p4_cases + 1;
      for (j = 0; j < 5; j = j+1) if (active_set[j]) p4_fault_instances = p4_fault_instances + 1;
      reset_dut(); load_reference(); apply_set(active_set);
      make_expected(active_set, expected_vector, expected_positions);
      vector_ok = (b_vec === expected_vector);
      if (!vector_ok) begin p4_vector_errors = p4_vector_errors + 1; errors = errors + 1; end
      retrieve_evidence();
      if (seen_positions !== expected_positions) begin p4_position_errors = p4_position_errors + 1; errors = errors + 1; end
      if (vector_ok && (seen_positions === expected_positions)) p4_correct = p4_correct + 1;
      release_set(active_set);
    end
  endtask

  initial begin
    errors = 0; overflow_events = 0; control_violation = 0; x_seen = 0;
    p3_opportunities = 0; p3_active_opportunities = 0; p3_correct = 0;
    p3_vector_errors = 0; p3_position_errors = 0;
    p4_cases = 0; p4_fault_instances = 0; p4_correct = 0;
    p4_vector_errors = 0; p4_position_errors = 0;

    // Two overlapping intermittent schedules over twelve diagnosis opportunities.
    run_phase3_case(5'b00000);
    run_phase3_case(5'b00001);
    run_phase3_case(5'b00101);
    run_phase3_case(5'b00100);
    run_phase3_case(5'b00000);
    run_phase3_case(5'b10010);
    run_phase3_case(5'b10000);
    run_phase3_case(5'b00010);
    run_phase3_case(5'b00000);
    run_phase3_case(5'b01100);
    run_phase3_case(5'b01000);
    run_phase3_case(5'b00000);

    $display("STEP3_PHASE3_SUMMARY opportunities=%0d active=%0d correct=%0d vector_errors=%0d position_errors=%0d",
      p3_opportunities, p3_active_opportunities, p3_correct, p3_vector_errors, p3_position_errors);
    if ((p3_correct == p3_opportunities) && (p3_vector_errors == 0) && (p3_position_errors == 0))
      $display("PASS: Step 3 Phase 3 intermittent fault schedules");
    else $display("FAIL: Step 3 Phase 3 intermittent fault schedules");

    // Exhaust every active subset of the five representative coordinates.
    for (subset_index = 0; subset_index < 32; subset_index = subset_index+1)
      run_phase4_case(subset_index[4:0]);

    $display("STEP3_PHASE4_SUMMARY subset_cases=%0d fault_instances=%0d correct=%0d vector_errors=%0d position_errors=%0d",
      p4_cases, p4_fault_instances, p4_correct, p4_vector_errors, p4_position_errors);
    if ((p4_correct == p4_cases) && (p4_vector_errors == 0) && (p4_position_errors == 0))
      $display("PASS: Step 3 Phase 4 exhaustive representative-subset statistics");
    else $display("FAIL: Step 3 Phase 4 exhaustive representative-subset statistics");

    if (overflow_events != 0) begin errors = errors + 1; $display("FAIL: tdf_pos overflow count %0d", overflow_events); end
    if (control_violation) begin errors = errors + 1; $display("FAIL: scan/spare enables overlapped"); end
    if (x_seen) begin errors = errors + 1; $display("FAIL: X observed on mismatch vector"); end
    if (errors == 0) $display("PASS: Step 3 Phase 3-4 combined regression");
    else $display("FAIL: Step 3 Phase 3-4 combined regression errors=%0d", errors);
    $finish;
  end
endmodule
