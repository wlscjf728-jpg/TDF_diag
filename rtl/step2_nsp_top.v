`timescale 1ns/1ps
`default_nettype none

module step2_nsp_top #(
  parameter integer L = 72,
  parameter integer N_TOTAL = 160,
  parameter integer NSP = 10,
  parameter integer NBANKS = N_TOTAL / NSP,
  parameter integer POS_W = (L <= 1) ? 1 : $clog2(L)
) (
  input wire clk_scan, input wire clk_spare, input wire rst_n,
  input wire se_scan, input wire se_spare, input wire ce_scan, input wire ce_spare,
  input wire oe,
  input wire cnt_en, input wire cnt_clr,
  input wire [N_TOTAL-1:0] scan_si, output wire [N_TOTAL-1:0] scan_so,
  input wire [NBANKS-1:0] spare_si, output wire [NBANKS-1:0] spare_so,
  input wire [N_TOTAL*L-1:0] mask, output wire [N_TOTAL*L-1:0] b_vec,
  input wire inject_result,
  output wire [NBANKS*POS_W-1:0] tdf_pos, output wire [NBANKS-1:0] tdf_valid
);
  genvar bank, col;
  generate
    for (bank = 0; bank < NBANKS; bank = bank + 1) begin : g_bank
      wire [NSP*L-1:0] bank_mask;
      wire [NSP*L-1:0] bank_b_vec;

      for (col = 0; col < L; col = col + 1) begin : g_column_map
        assign bank_mask[(col*NSP) +: NSP] =
          mask[(col*N_TOTAL) + (bank*NSP) +: NSP];
        assign b_vec[(col*N_TOTAL) + (bank*NSP) +: NSP] =
          bank_b_vec[(col*NSP) +: NSP];
      end

      spare_scan_top #(.L(L), .NCHAINS(NSP), .POS_W(POS_W)) u_bank (
        .clk_scan(clk_scan), .clk_spare(clk_spare), .rst_n(rst_n),
        .se_scan(se_scan), .se_spare(se_spare),
        .ce_scan(ce_scan), .ce_spare(ce_spare), .oe(oe),
        .cnt_en(cnt_en), .cnt_clr(cnt_clr),
        .scan_si(scan_si[(bank*NSP) +: NSP]),
        .scan_so(scan_so[(bank*NSP) +: NSP]),
        .spare_si(spare_si[bank]), .spare_so(spare_so[bank]),
        .mask(bank_mask), .b_vec(bank_b_vec),
        .inject_result(inject_result),
        .tdf_pos(tdf_pos[(bank*POS_W) +: POS_W]),
        .tdf_valid(tdf_valid[bank])
      );
    end
  endgenerate
endmodule

module step2_scan_baseline #(
  parameter integer L = 72,
  parameter integer N_TOTAL = 160
) (
  input wire clk_scan, input wire rst_n,
  input wire se_scan, input wire ce_scan,
  input wire [N_TOTAL-1:0] scan_si, output wire [N_TOTAL-1:0] scan_so
);
  wire [N_TOTAL*(L+1)-1:0] scan_path;
  assign scan_path[0 +: N_TOTAL] = scan_si;

  genvar col, chain;
  generate
    for (col = 0; col < L; col = col + 1) begin : g_col
      for (chain = 0; chain < N_TOTAL; chain = chain + 1) begin : g_chain
        scan_dff u_scan_ff (
          .clk(clk_scan), .rst_n(rst_n), .se(se_scan), .ce(ce_scan),
          .d(1'b0),
          .si(scan_path[(col*N_TOTAL) + chain]),
          .q(scan_path[((col+1)*N_TOTAL) + chain])
        );
      end
    end
  endgenerate

  assign scan_so = scan_path[(L*N_TOTAL) +: N_TOTAL];
endmodule

`default_nettype wire
