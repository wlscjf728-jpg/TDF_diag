`timescale 1ns/1ps

module TB_step2_phase1;
  localparam L = 4;
  localparam N_TOTAL = 4;
  localparam NSP = 2;
  localparam NBANKS = N_TOTAL / NSP;
  localparam POS_W = 2;

  reg clk_scan, clk_spare, rst_n;
  reg se_scan, se_spare, ce_scan, ce_spare, oe;
  reg cnt_en, cnt_clr, inject_result;
  reg [N_TOTAL-1:0] scan_si;
  wire [N_TOTAL-1:0] scan_so;
  reg [NBANKS-1:0] spare_si;
  wire [NBANKS-1:0] spare_so;
  reg [N_TOTAL*L-1:0] mask;
  wire [N_TOTAL*L-1:0] b_vec;
  wire [NBANKS*POS_W-1:0] tdf_pos;
  wire [NBANKS-1:0] tdf_valid;

  reg base_clk_scan, base_rst_n, base_se_scan, base_ce_scan;
  reg [N_TOTAL-1:0] base_scan_si;
  wire [N_TOTAL-1:0] base_scan_so;

  integer i, errors;
  reg saw_bank0, saw_bank1;

  step2_nsp_top #(.L(L), .N_TOTAL(N_TOTAL), .NSP(NSP)) DUT (
    .clk_scan(clk_scan), .clk_spare(clk_spare), .rst_n(rst_n),
    .se_scan(se_scan), .se_spare(se_spare), .ce_scan(ce_scan), .ce_spare(ce_spare),
    .oe(oe), .cnt_en(cnt_en), .cnt_clr(cnt_clr),
    .scan_si(scan_si), .scan_so(scan_so),
    .spare_si(spare_si), .spare_so(spare_so),
    .mask(mask), .b_vec(b_vec), .inject_result(inject_result),
    .tdf_pos(tdf_pos), .tdf_valid(tdf_valid)
  );

  step2_scan_baseline #(.L(L), .N_TOTAL(N_TOTAL)) BASE (
    .clk_scan(base_clk_scan), .rst_n(base_rst_n),
    .se_scan(base_se_scan), .ce_scan(base_ce_scan),
    .scan_si(base_scan_si), .scan_so(base_scan_so)
  );

  initial begin clk_scan = 0; forever #5 clk_scan = ~clk_scan; end
  initial begin clk_spare = 0; forever #10 clk_spare = ~clk_spare; end
  initial begin base_clk_scan = 0; forever #5 base_clk_scan = ~base_clk_scan; end

  task pulse_spare;
    begin ce_spare = 1; @(posedge clk_spare); #1 ce_spare = 0; end
  endtask

  task reset_all;
    begin
      rst_n = 0; base_rst_n = 0;
      se_scan = 0; se_spare = 0; ce_scan = 0; ce_spare = 0; oe = 0;
      cnt_en = 0; cnt_clr = 0; inject_result = 0;
      scan_si = 0; spare_si = 0; mask = 0;
      base_se_scan = 0; base_ce_scan = 0; base_scan_si = 0;
      #21 rst_n = 1; base_rst_n = 1; #2;
    end
  endtask

  task check_baseline_shift;
    begin
      base_se_scan = 1; base_ce_scan = 1;
      base_scan_si = 4'b1010;
      repeat (L) @(posedge base_clk_scan);
      #1;
      if (base_scan_so !== 4'b1010) begin
        errors = errors + 1;
        $display("FAIL: baseline shift output=%b", base_scan_so);
      end
      base_ce_scan = 0; base_se_scan = 0;
    end
  endtask

  task load_distinct_references;
    begin
      se_spare = 1;
      for (i = L - 1; i >= 0; i = i - 1) begin
        spare_si[0] = (i == 1);
        spare_si[1] = (i == 3);
        pulse_spare();
      end
      se_spare = 0; spare_si = 0;
    end
  endtask

  task capture_no_fault;
    begin
      @(negedge clk_scan); oe = 1; ce_scan = 1;
      @(posedge clk_scan); #1 ce_scan = 0; oe = 0; #1;
      if (b_vec !== 0) begin
        errors = errors + 1;
        $display("FAIL: multi-bank no-fault mismatch=%h", b_vec);
      end
    end
  endtask

  task inject_and_retrieve_bank_evidence;
    begin
      force DUT.g_bank[0].u_bank.g_col[1].u_col.g_sc[0].scan_d = 1'b0;
      force DUT.g_bank[1].u_bank.g_col[3].u_col.g_sc[1].scan_d = 1'b0;
      @(negedge clk_scan); oe = 1; ce_scan = 1;
      @(posedge clk_scan); #1 ce_scan = 0; oe = 0;
      release DUT.g_bank[0].u_bank.g_col[1].u_col.g_sc[0].scan_d;
      release DUT.g_bank[1].u_bank.g_col[3].u_col.g_sc[1].scan_d;

      inject_result = 1; pulse_spare(); inject_result = 0;
      cnt_clr = 1; @(posedge clk_spare); #1 cnt_clr = 0;
      cnt_en = 1; se_spare = 1; saw_bank0 = 0; saw_bank1 = 0;
      for (i = 0; i < L; i = i + 1) begin
        pulse_spare();
        if (tdf_valid[0] && tdf_pos[0 +: POS_W] == 1) saw_bank0 = 1;
        if (tdf_valid[1] && tdf_pos[POS_W +: POS_W] == 3) saw_bank1 = 1;
      end
      cnt_en = 0; se_spare = 0;
      if (!saw_bank0 || !saw_bank1) begin
        errors = errors + 1;
        $display("FAIL: bank evidence bank0=%b bank1=%b", saw_bank0, saw_bank1);
      end
    end
  endtask

  initial begin
    errors = 0; saw_bank0 = 0; saw_bank1 = 0;
    reset_all();
    check_baseline_shift();
    load_distinct_references();
    capture_no_fault();
    inject_and_retrieve_bank_evidence();
    if (errors == 0) $display("PASS: Step 2 Phase 1 multi-bank wrapper and baseline");
    else $display("FAIL: Step 2 Phase 1 errors=%0d", errors);
    $finish;
  end
endmodule
