// Step 4.5 timing-isolation structures. These tops intentionally contain only
// shift-chain elements so PrimeTime results cannot be dominated by control logic.

module step4_5_scan_ff_only #(
    parameter L = 72
) (
    input  wire clk_scan,
    input  wire chain_in,
    output wire chain_out
);
    reg [L-1:0] stage_q;

    always @(posedge clk_scan) begin
        stage_q <= {stage_q[L-2:0], chain_in};
    end

    assign chain_out = stage_q[L-1];
endmodule

module step4_5_scan_mux_ff #(
    parameter L = 72
) (
    input  wire clk_scan,
    input  wire se,
    input  wire chain_in,
    input  wire [L-1:0] func_d,
    output wire chain_out
);
    reg [L-1:0] stage_q;
    wire [L-1:0] scan_d;
    wire [L-1:0] mux_d;

    assign scan_d[0] = chain_in;
    genvar m;
    generate
        for (m = 1; m < L; m = m + 1) begin : g_scan_link
            assign scan_d[m] = stage_q[m-1];
        end
    endgenerate

    assign mux_d = se ? scan_d : func_d;

    always @(posedge clk_scan) begin
        stage_q <= mux_d;
    end

    assign chain_out = stage_q[L-1];
endmodule


module step4_5_spare_ff_only #(
    parameter L = 72
) (
    input  wire clk_spare,
    input  wire chain_in,
    output wire chain_out
);
    reg [L-1:0] stage_q;

    always @(posedge clk_spare) begin
        stage_q <= {stage_q[L-2:0], chain_in};
    end

    assign chain_out = stage_q[L-1];
endmodule

module step4_5_forced_lockup_stage (
    input  wire clk_ff,
    input  wire clk_latch,
    input  wire d,
    output reg  q,
    output wire q_latched
);
    always @(posedge clk_ff) begin
        q <= d;
    end

    // SAED32 RVT has a positive-level latch but no native negative-level latch.
    // The explicit, preserved inverter makes this latch transparent while the
    // source spare clock is low, matching the intended lock-up phase.
    (* dont_touch = "true" *) LATCHX1_RVT u_lockup_latch (
        .D   (q),
        .CLK (clk_latch),
        .Q   (q_latched)
    );
endmodule

module step4_5_spare_forced_lockup #(
    parameter L = 72
) (
    input  wire clk_spare,
    input  wire chain_in,
    output wire chain_out
);
    wire clk_spare_n;
    wire [L-1:0] stage_q;
    wire [L-2:0] latch_q;

    (* dont_touch = "true" *) INVX1_RVT u_lockup_clk_inv (
        .A (clk_spare),
        .Y (clk_spare_n)
    );

    genvar i;
    generate
        for (i = 0; i < L; i = i + 1) begin : g_stage
            wire stage_d;
            if (i == 0) begin : g_first
                assign stage_d = chain_in;
            end else begin : g_following
                assign stage_d = latch_q[i-1];
            end

            if (i == L-1) begin : g_last
                reg q_reg;
                always @(posedge clk_spare) q_reg <= stage_d;
                assign stage_q[i] = q_reg;
            end else begin : g_with_lockup
                step4_5_forced_lockup_stage u_stage (
                    .clk_ff     (clk_spare),
                    .clk_latch  (clk_spare_n),
                    .d         (stage_d),
                    .q         (stage_q[i]),
                    .q_latched (latch_q[i])
                );
            end
        end
    endgenerate

    assign chain_out = stage_q[L-1];
endmodule
