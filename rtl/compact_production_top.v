`timescale 1ns/1ps
`default_nettype none

module compact_column_slice #(parameter integer NCHAINS = 5) (
  input wire clk_scan, input wire clk_spare, input wire rst_n,
  input wire [NCHAINS-1:0] prev_scan_q,
  output wire [NCHAINS-1:0] this_scan_q,
  input wire inject_result,
  input wire se_scan, input wire se_spare, input wire ce_scan, input wire ce_spare,
  input wire copy_enable,
  input wire si_spare, output wire so_spare,
  input wire [NCHAINS-1:0] si_scan, output wire [NCHAINS-1:0] so_scan
);
  wire [NCHAINS-1:0] scan_q;
  wire [NCHAINS-1:0] mismatch_vec;
  wire mismatch_bit = |mismatch_vec;
  wire spare_q, spare_q_lu;
  wire spare_d = inject_result ? mismatch_bit : 1'b0;

  scan_dff u_spare_ff (
    .clk(clk_spare), .rst_n(rst_n), .se(se_spare), .ce(ce_spare),
    .d(spare_d), .si(si_spare), .q(spare_q)
  );
  neg_lockup_latch u_spare_lu (.clk(clk_spare), .d(spare_q), .q(spare_q_lu));
  assign so_spare = spare_q_lu;

  genvar c;
  generate
    for (c = 0; c < NCHAINS; c = c + 1) begin : g_sc
      wire scan_d = copy_enable ? spare_q_lu : prev_scan_q[c];
      scan_dff u_scan_ff (
        .clk(clk_scan), .rst_n(rst_n), .se(se_scan), .ce(ce_scan),
        .d(scan_d), .si(si_scan[c]), .q(scan_q[c])
      );
      assign this_scan_q[c] = scan_q[c];
      assign so_scan[c] = scan_q[c];
      assign mismatch_vec[c] = scan_q[c] ^ spare_q_lu;
    end
  endgenerate
endmodule

module compact_spare_scan_bank #(
  parameter integer L = 72,
  parameter integer NCHAINS = 5,
  parameter integer POS_W = (L <= 1) ? 1 : $clog2(L)
) (
  input wire clk_scan, input wire clk_spare, input wire rst_n,
  input wire se_scan, input wire se_spare, input wire ce_scan, input wire ce_spare,
  input wire oe,
  input wire cnt_en, input wire cnt_clr,
  input wire [NCHAINS-1:0] scan_si, output wire [NCHAINS-1:0] scan_so,
  input wire spare_si, output wire spare_so,
  input wire inject_result,
  output wire [POS_W-1:0] tdf_pos, output wire tdf_valid
);
  wire [NCHAINS*(L+1)-1:0] w_scan_flat;
  wire [L:0] w_spare;
  wire [NCHAINS*L-1:0] scan_q_col_flat;
  reg oe_q;
  wire copy_enable = oe & ~oe_q;

  always @(posedge clk_scan or negedge rst_n) begin
    if (!rst_n) oe_q <= 1'b0;
    else oe_q <= oe;
  end

  assign w_spare[0] = spare_si;
  assign w_scan_flat[0 +: NCHAINS] = scan_si;

  genvar k;
  generate
    for (k = 0; k < L; k = k + 1) begin : g_col
      wire [NCHAINS-1:0] prev_scan_q;
      wire [NCHAINS-1:0] this_scan_q;
      wire [NCHAINS-1:0] so_scan_vec;
      if (k == 0) begin : g_first_column
        assign prev_scan_q = {NCHAINS{1'b0}};
      end else begin : g_later_column
        assign prev_scan_q = scan_q_col_flat[((k-1)*NCHAINS) +: NCHAINS];
      end

      compact_column_slice #(.NCHAINS(NCHAINS)) u_col (
        .clk_scan(clk_scan), .clk_spare(clk_spare), .rst_n(rst_n),
        .prev_scan_q(prev_scan_q), .this_scan_q(this_scan_q),
        .inject_result(inject_result),
        .se_scan(se_scan), .se_spare(se_spare), .ce_scan(ce_scan), .ce_spare(ce_spare),
        .copy_enable(copy_enable),
        .si_spare(w_spare[k]), .so_spare(w_spare[k+1]),
        .si_scan(w_scan_flat[(k*NCHAINS) +: NCHAINS]), .so_scan(so_scan_vec)
      );
      assign w_scan_flat[((k+1)*NCHAINS) +: NCHAINS] = so_scan_vec;
      assign scan_q_col_flat[(k*NCHAINS) +: NCHAINS] = this_scan_q;
    end
  endgenerate

  assign spare_so = w_spare[L];
  assign scan_so = w_scan_flat[(L*NCHAINS) +: NCHAINS];

  bit_position_counter #(.LENGTH(L), .INDEX_W(POS_W)) u_bit_position_counter (
    .clk(clk_spare), .rst_n(rst_n), .en(cnt_en), .clr(cnt_clr), .bit_in(spare_so),
    .pos(tdf_pos), .valid(tdf_valid)
  );
endmodule

module compact_production_top #(
  parameter integer L = 72,
  parameter integer N_TOTAL = 160,
  parameter integer NSP = 20,
  parameter integer NBANKS = N_TOTAL / NSP,
  parameter integer POS_W = (L <= 1) ? 1 : $clog2(L)
) (
  input wire clk_scan, input wire clk_spare, input wire rst_n,
  input wire se_scan, input wire se_spare, input wire ce_scan, input wire ce_spare,
  input wire oe,
  input wire cnt_en, input wire cnt_clr,
  input wire [N_TOTAL-1:0] scan_si, output wire [N_TOTAL-1:0] scan_so,
  input wire [NBANKS-1:0] spare_si, output wire [NBANKS-1:0] spare_so,
  input wire inject_result,
  output wire [NBANKS*POS_W-1:0] tdf_pos, output wire [NBANKS-1:0] tdf_valid
);
  genvar bank;
  generate
    for (bank = 0; bank < NBANKS; bank = bank + 1) begin : g_bank
      compact_spare_scan_bank #(.L(L), .NCHAINS(NSP), .POS_W(POS_W)) u_bank (
        .clk_scan(clk_scan), .clk_spare(clk_spare), .rst_n(rst_n),
        .se_scan(se_scan), .se_spare(se_spare),
        .ce_scan(ce_scan), .ce_spare(ce_spare), .oe(oe),
        .cnt_en(cnt_en), .cnt_clr(cnt_clr),
        .scan_si(scan_si[(bank*NSP) +: NSP]),
        .scan_so(scan_so[(bank*NSP) +: NSP]),
        .spare_si(spare_si[bank]), .spare_so(spare_so[bank]),
        .inject_result(inject_result),
        .tdf_pos(tdf_pos[(bank*POS_W) +: POS_W]),
        .tdf_valid(tdf_valid[bank])
      );
    end
  endgenerate
endmodule

`default_nettype wire
