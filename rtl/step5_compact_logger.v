`timescale 1ns/1ps
`default_nettype none

module step5_compact_logger #(
  parameter integer L = 72,
  parameter integer MAX_EVENTS = 32,
  parameter integer POS_W = (L <= 1) ? 1 : $clog2(L),
  parameter integer RECORD_W = 16,
  parameter integer COUNT_W = 8
) (
  input  wire [L-1:0] b00,
  input  wire [L-1:0] b11,
  input  wire [L-1:0] b01,
  input  wire [L-1:0] b10,
  output reg  [MAX_EVENTS*RECORD_W-1:0] records,
  output reg  [COUNT_W-1:0] stored_events,
  output reg  [COUNT_W-1:0] detected_events,
  output reg  overflow
);
  integer k;
  integer wr;
  reg [3:0] mask;
  reg [1:0] syndrome;
  reg [5:0] metadata;
  reg [RECORD_W-1:0] record;

  always @* begin
    records = {MAX_EVENTS*RECORD_W{1'b0}};
    stored_events = {COUNT_W{1'b0}};
    detected_events = {COUNT_W{1'b0}};
    overflow = 1'b0;
    wr = 0;

    for (k = 0; k < L; k = k + 1) begin
      mask = {b10[k], b01[k], b11[k], b00[k]};
      if (|mask) begin
        detected_events = detected_events + {{(COUNT_W-1){1'b0}}, 1'b1};

        // 2-bit syndrome class used by the report format:
        // 00: static/equal-pattern class, 01: 0->1 transition class,
        // 10: 1->0 transition class, 11: mixed or multi-pattern ambiguity.
        if ((mask & (mask - 1'b1)) != 4'b0000) begin
          syndrome = 2'b11;
        end else if (b01[k]) begin
          syndrome = 2'b01;
        end else if (b10[k]) begin
          syndrome = 2'b10;
        end else begin
          syndrome = 2'b00;
        end

        // metadata[5] marks mixed/multi-pattern evidence; metadata[3:0]
        // preserves the pattern-hit mask for offline FA interpretation.
        metadata = {((mask & (mask - 1'b1)) != 4'b0000), 1'b0, mask};
        record = {1'b1, k[POS_W-1:0], metadata, syndrome};

        if (wr < MAX_EVENTS) begin
          records[wr*RECORD_W +: RECORD_W] = record;
          wr = wr + 1;
          stored_events = stored_events + {{(COUNT_W-1){1'b0}}, 1'b1};
        end else begin
          overflow = 1'b1;
        end
      end
    end
  end
endmodule

`default_nettype wire
