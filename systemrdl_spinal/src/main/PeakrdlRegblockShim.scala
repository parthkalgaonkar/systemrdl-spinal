package systemrdl_spinal

import spinal.core._
import os.Path

class PeakrdlRegblockShim[T_in <: Bundle, T_out <: Bundle](
  in_type: HardType[T_in],
  out_type: HardType[T_out],
  addr_width: Int,
  data_width: Int
) extends BlackBox {
  val io = new Bundle {
    val clk = in Bool()
    val rst = in Bool()  // This is always called rst irrespective of reset type
    val s_cpuif = PeakrdlCpuIf(addr_width, data_width)
    val hwif_in = in (in_type())
    val hwif_out = out (out_type())
  }

  mapCurrentClockDomain(io.clk, io.rst)

  noIoPrefix()
}
