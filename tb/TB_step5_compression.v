`timescale 1ns/1ps
`default_nettype none

module TB_step5_compression;
  localparam integer L = 72;
  localparam integer NSP = 10;
  localparam integer PATTERNS = 4;
  localparam integer MAX_EVENTS = 32;
  localparam integer RECORD_W = 16;
  localparam integer SRAM_BITS = 512;
  localparam integer POS_W = 7;
  localparam integer COUNT_W = 8;
  localparam integer FULL_BITS = NSP * L * PATTERNS;
  localparam integer RAW_B_BITS = L * PATTERNS;

  reg [L-1:0] b00, b11, b01, b10;
  wire [MAX_EVENTS*RECORD_W-1:0] records;
  wire [COUNT_W-1:0] stored_events;
  wire [COUNT_W-1:0] detected_events;
  wire overflow;

  integer errors;
  integer csv;
  integer i;

  step5_compact_logger #(
    .L(L), .MAX_EVENTS(MAX_EVENTS), .POS_W(POS_W),
    .RECORD_W(RECORD_W), .COUNT_W(COUNT_W)
  ) dut (
    .b00(b00), .b11(b11), .b01(b01), .b10(b10),
    .records(records), .stored_events(stored_events),
    .detected_events(detected_events), .overflow(overflow)
  );

  function real reduction_pct;
    input integer compact_bits;
    input integer base_bits;
    begin
      reduction_pct = (1.0 - (compact_bits * 1.0 / base_bits)) * 100.0;
    end
  endfunction

  task clear_vectors;
    begin
      b00 = {L{1'b0}};
      b11 = {L{1'b0}};
      b01 = {L{1'b0}};
      b10 = {L{1'b0}};
    end
  endtask

  task check_record;
    input integer idx;
    input integer exp_loc;
    input [1:0] exp_syn;
    reg [RECORD_W-1:0] rec;
    begin
      rec = records[idx*RECORD_W +: RECORD_W];
      if (rec[15] !== 1'b1 || rec[14:8] !== exp_loc[6:0] || rec[1:0] !== exp_syn) begin
        $display("FAIL: record[%0d] got=%h exp_valid=1 exp_loc=%0d exp_syn=%b", idx, rec, exp_loc, exp_syn);
        errors = errors + 1;
      end
    end
  endtask

  task run_case;
    input [160*8-1:0] name;
    input integer exp_detected;
    input integer exp_stored;
    input exp_overflow;
    integer compact_bits;
    real red_full;
    real red_raw;
    real sram_use;
    begin
      #1;
      compact_bits = stored_events * RECORD_W;
      red_full = reduction_pct(compact_bits, FULL_BITS);
      red_raw = reduction_pct(compact_bits, RAW_B_BITS);
      sram_use = (compact_bits * 100.0) / SRAM_BITS;

      $display("CASE %-20s detected=%0d stored=%0d compact_bits=%0d red_full=%0.2f%% red_rawB=%0.2f%% sram_use=%0.2f%% overflow=%0d",
               name, detected_events, stored_events, compact_bits, red_full, red_raw, sram_use, overflow);
      $fdisplay(csv, "%0s,%0d,%0d,%0d,%0d,%0d,%0.2f,%0.2f,%0.2f,%0d",
                name, FULL_BITS, RAW_B_BITS, detected_events, stored_events, compact_bits,
                red_full, red_raw, sram_use, overflow);

      if (detected_events !== exp_detected[COUNT_W-1:0]) begin
        $display("FAIL: %0s detected got=%0d exp=%0d", name, detected_events, exp_detected);
        errors = errors + 1;
      end
      if (stored_events !== exp_stored[COUNT_W-1:0]) begin
        $display("FAIL: %0s stored got=%0d exp=%0d", name, stored_events, exp_stored);
        errors = errors + 1;
      end
      if (overflow !== exp_overflow) begin
        $display("FAIL: %0s overflow got=%0d exp=%0d", name, overflow, exp_overflow);
        errors = errors + 1;
      end
    end
  endtask

  initial begin
    errors = 0;
    csv = $fopen("step5_compression_summary.csv", "w");
    if (csv == 0) begin
      $display("FAIL: could not open step5_compression_summary.csv");
      $finish;
    end
    $fdisplay(csv, "case,full_response_bits,raw_b_bits,detected_events,stored_events,compact_log_bits,reduction_vs_full_pct,reduction_vs_rawB_pct,sram_usage_pct,overflow");

    clear_vectors();
    run_case("no_fault", 0, 0, 1'b0);

    clear_vectors();
    b00[37] = 1'b1;
    run_case("single_static", 1, 1, 1'b0);
    check_record(0, 37, 2'b00);

    clear_vectors();
    b01[20] = 1'b1;
    run_case("single_transition", 1, 1, 1'b0);
    check_record(0, 20, 2'b01);

    clear_vectors();
    b00[5]  = 1'b1;
    b11[17] = 1'b1;
    b10[52] = 1'b1;
    run_case("multi_diff_cols", 3, 3, 1'b0);
    check_record(0, 5,  2'b00);
    check_record(1, 17, 2'b00);
    check_record(2, 52, 2'b10);

    clear_vectors();
    b00[37] = 1'b1;
    b01[37] = 1'b1;
    b10[37] = 1'b1;
    run_case("same_col_mixed", 1, 1, 1'b0);
    check_record(0, 37, 2'b11);

    clear_vectors();
    for (i = 0; i < 16; i = i + 1) begin
      if ((i % 3) == 0) b00[i] = 1'b1;
      else if ((i % 3) == 1) b01[i] = 1'b1;
      else b10[i] = 1'b1;
    end
    run_case("dense_16_events", 16, 16, 1'b0);

    clear_vectors();
    for (i = 0; i < 40; i = i + 1) begin
      if ((i % 2) == 0) b01[i] = 1'b1;
      else b10[i] = 1'b1;
    end
    run_case("overflow_40_events", 40, 32, 1'b1);

    $fclose(csv);
    if (errors == 0) $display("PASS: Step 5 compact compression experiment");
    else $display("FAIL: Step 5 compact compression experiment errors=%0d", errors);
    $finish;
  end
endmodule

`default_nettype wire
