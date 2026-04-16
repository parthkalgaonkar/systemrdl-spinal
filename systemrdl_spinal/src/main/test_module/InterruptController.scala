package systemrdl_spinal.test_module

import spinal.core._
import systemrdl_spinal._


case class HwifInBundle() extends Bundle {
  case class RAW_PENDING_REG_bundle() extends Bundle {
    case class raw_pending_bundle() extends Bundle {
      val next = Bits(15 bits)
    }
    val raw_pending = raw_pending_bundle()
  }
  val RAW_PENDING_REG = RAW_PENDING_REG_bundle()
}

case class HwifOutBundle() extends Bundle {
  case class TOP_CTRL_bundle() extends Bundle {
    case class enable_bundle() extends Bundle {
      val value = Bool()
    }
    val enable = enable_bundle()
  }

  case class SOURCE_MASK_REG_bundle() extends Bundle {
    case class source_mask_bundle() extends Bundle {
      val value = Bits(15 bits)
    }
    val source_mask = source_mask_bundle()
  }

  case class RAW_PENDING_REG_bundle() extends Bundle {
    case class raw_pending_bundle() extends Bundle {
      val value = Bits(15 bits)
    }
    val raw_pending = raw_pending_bundle()
  }

  case class INTERRUPT_VECTOR_REG_bundle() extends Bundle {
    case class interrupt_vector_bundle() extends Bundle {
      val value = Bits(32 bits)
    }
    val interrupt_vector = interrupt_vector_bundle()
  }
  val TOP_CTRL = TOP_CTRL_bundle()
  val SOURCE_MASK_REG = SOURCE_MASK_REG_bundle()
  val RAW_PENDING_REG = RAW_PENDING_REG_bundle()
  val INTERRUPT_VECTOR_REG = Vec.fill(15)(INTERRUPT_VECTOR_REG_bundle())
}

class InterruptController extends PeakrdlRegblockShim(
  HwifInBundle(),
  HwifOutBundle(),
  9,
  32
)


object InterruptController extends App {
  class InterruptControllerTop extends Component {
    val io = new Bundle {
      val cpuif = PeakrdlCpuIf(
        9, 32
      )
      val hwif_in = in (HwifInBundle())
      val hwif_out = out (HwifOutBundle())
    }

    val regblock = new InterruptController()
    regblock.io.s_cpuif <> io.cpuif
    regblock.io.hwif_in := io.hwif_in
    io.hwif_out := regblock.io.hwif_out
  }

  val config = SpinalConfig(
    withTimescale = false,
    targetDirectory = "gen",
    oneFilePerComponent = true,
    genLineComments = true
  )

  config.generateSystemVerilog(new InterruptControllerTop())
}
