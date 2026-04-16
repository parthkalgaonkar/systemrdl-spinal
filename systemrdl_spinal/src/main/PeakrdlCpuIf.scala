package systemrdl_spinal

import spinal.core._

case class PeakrdlCpuIf(addr_width: Int, data_width: Int) extends Bundle {
  val req = in Bool()
  val req_is_wr = in Bool()
  val addr = in Bits(addr_width bits)
  val wr_data = in Bits(data_width bits)
  val wr_biten = in Bits(data_width bits)
  val req_stall_wr = out Bool()
  val req_stall_rd = out Bool()
  val rd_ack = out Bool()
  val rd_err = out Bool()
  val rd_data = out Bits(data_width bits)
  val wr_ack = out Bool()
  val wr_err = out Bool()
}
