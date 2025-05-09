#include "llvm/IR/DebugLoc.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/Instruction.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/IntrinsicInst.h"
#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Verifier.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/ManagedStatic.h"
#include "llvm/Support/SMLoc.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/IR/InstrTypes.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/Transforms/Utils/CodeExtractor.h"

#include "phasar.h"

#include <filesystem>
#include <string>
#include <utility>
#include <set>
#include <algorithm>
#include <fstream>

// the set of ISRs
std::set<llvm::Function*> ISRs;
// the set of Global Variables read from in ISRs
std::set<std::string> R;
// the set of Global Variables written to in ISRs
std::set<std::string> W;

std::ofstream output("output.txt");

// find all the ISRs
void findISRs(std::unique_ptr<llvm::Module> &M) {
  llvm::outs() << "\n///////Finding ISRs///////\n";
  output << "ISRs:\n";
  // go over every function in the module
  for (auto &F : *M) {
    // go over every basic block in the function
    for (auto &BB : F) {
      // go over every instruction in the basic block
      for (auto &I : BB) {
        // it its a call instruction
        if (auto CI = llvm::dyn_cast<llvm::CallInst>(&I)) {
          // check if its calling attachInterrupt
          auto *Calle = CI->getCalledFunction();
          if (Calle && Calle->getName().contains("attachInterrupt")) {
            // get the function sent as an argument
            auto *ISRarg = CI->getOperand(0);
            if (auto *ISR = llvm::dyn_cast<llvm::Function>(ISRarg->stripPointerCasts())){
              output << llvm::demangle(ISRarg->getName().str()) << "\n";
              llvm::outs() << "\nAdded ISR: " << llvm::demangle(ISRarg->getName().str()) << "\n";
              // save it to the set of ISRs
              ISRs.insert(ISR);
            }
          }
        }
      }
    }
  }
  return;
}

// checks if the instruction may read from memory
// and checks if its reading from a global variable
// if both true return the global variable
// return nullptr otherwise
const llvm::GlobalVariable* getGlobalVariableRead(const llvm::Instruction* I) {
  // check if the instruction may read from memory
  if (I->mayReadFromMemory()) {
    // check if its a load instruction
    if (llvm::isa<llvm::LoadInst>(I)) {
      // get the pointer of the memory location its read from
      auto SI = llvm::dyn_cast<llvm::LoadInst>(I);
      auto Iptr = SI->getPointerOperand();

      // check if its for a global variable
      if (llvm::isa<llvm::GlobalVariable>(Iptr)) {
        // print the instruction
        //I->print(llvm::outs());
        // llvm::outs() << '\n';

        // return the global variable
        return llvm::dyn_cast<llvm::GlobalVariable>(Iptr);
      }
    }
    // check if its a cmpxchg instruction
    if (llvm::isa<llvm::AtomicCmpXchgInst>(I)) {
      // get the pointer of the memory location its read from
      auto SI = llvm::dyn_cast<llvm::AtomicCmpXchgInst>(I);
      auto Iptr = SI->getPointerOperand();

      // check if its for a global variable
      if (llvm::isa<llvm::GlobalVariable>(Iptr)) {
        // print the instruction
        //I->print(llvm::outs());
        // llvm::outs() << '\n';

        // return the global variable
        return llvm::dyn_cast<llvm::GlobalVariable>(Iptr);
      }
    }
    // check if its an atomicrmw instruction
    if (llvm::isa<llvm::AtomicRMWInst>(I)) {
      // get the pointer of the memory location its read from
      auto SI = llvm::dyn_cast<llvm::AtomicRMWInst>(I);
      auto Iptr = SI->getPointerOperand();

      // check if its for a global variable
      if (llvm::isa<llvm::GlobalVariable>(Iptr)) {
        // print the instruction
        //I->print(llvm::outs());
        // llvm::outs() << '\n';

        // return the global variable
        return llvm::dyn_cast<llvm::GlobalVariable>(Iptr);
      }
    }
    // check if its a call instruction
    if (llvm::isa<llvm::CallInst>(I)) {
      // loop over arguments
      auto SI = llvm::dyn_cast<llvm::CallInst>(I);
      for (unsigned i=0; i < SI->getNumOperands()-1; ++i) {
        auto Iptr = SI->getOperand(i+1);
        // check if its for a global variable
        if (llvm::isa<llvm::GlobalVariable>(Iptr)) {
          // print the instruction
          //I->print(llvm::outs());
          // llvm::outs() << '\n';

          // return the global variable
          return llvm::dyn_cast<llvm::GlobalVariable>(Iptr);
        }
      }
    }
    // check if its an invoke instruction
    if (llvm::isa<llvm::InvokeInst>(I)) {
      // loop over arguments
      auto SI = llvm::dyn_cast<llvm::InvokeInst>(I);
      for (unsigned i=0; i < SI->getNumOperands()-1; ++i) {
        auto Iptr = SI->getOperand(i+1);
        // check if its for a global variable
        if (llvm::isa<llvm::GlobalVariable>(Iptr)) {
          // print the instruction
          //I->print(llvm::outs());
          // llvm::outs() << '\n';

          // return the global variable
          return llvm::dyn_cast<llvm::GlobalVariable>(Iptr);
        }
      }
    }
    // check if its a callbr instruction
    if (llvm::isa<llvm::CallBrInst>(I)) {
      // loop over arguments
      auto SI = llvm::dyn_cast<llvm::CallBrInst>(I);
      for (unsigned i=0; i < SI->getNumOperands()-1; ++i) {
        auto Iptr = SI->getOperand(i+1);
        // check if its for a global variable
        if (llvm::isa<llvm::GlobalVariable>(Iptr)) {
          // print the instruction
          //I->print(llvm::outs());
          // llvm::outs() << '\n';

          // return the global variable
          return llvm::dyn_cast<llvm::GlobalVariable>(Iptr);
        }
      }
    }
  }
  return nullptr;
}

// checks if the instruction may write to memory
// and checks if its writing to a global variable
// if both true return the global variable
// return nullptr otherwise
const llvm::GlobalVariable* getGlobalVariableWrite(const llvm::Instruction* I) {
  // check if the instruction may write to memory
  if (I->mayWriteToMemory()) {
    // check if its a store instruction
    if (llvm::isa<llvm::StoreInst>(I)) {
      // get the pointer of the memory location its written to
      auto SI = llvm::dyn_cast<llvm::StoreInst>(I);
      auto Iptr = SI->getPointerOperand();

      // check if its for a global variable
      if (llvm::isa<llvm::GlobalVariable>(Iptr)) {
        // print the instruction
        //I->print(llvm::outs());
        // llvm::outs() << '\n';

        // return the global variable
        return llvm::dyn_cast<llvm::GlobalVariable>(Iptr);
      }
    }
    // check if its a cmpxchg instruction
    if (llvm::isa<llvm::AtomicCmpXchgInst>(I)) {
      // get the pointer of the memory location its written to
      auto SI = llvm::dyn_cast<llvm::AtomicCmpXchgInst>(I);
      auto Iptr = SI->getPointerOperand();

      // check if its for a global variable
      if (llvm::isa<llvm::GlobalVariable>(Iptr)) {
        // print the instruction
        //I->print(llvm::outs());
        // llvm::outs() << '\n';

        // return the global variable
        return llvm::dyn_cast<llvm::GlobalVariable>(Iptr);
      }
    }
    // check if its an atomicrmw instruction
    if (llvm::isa<llvm::AtomicRMWInst>(I)) {
      // get the pointer of the memory location its written to
      auto SI = llvm::dyn_cast<llvm::AtomicRMWInst>(I);
      auto Iptr = SI->getPointerOperand();

      // check if its for a global variable
      if (llvm::isa<llvm::GlobalVariable>(Iptr)) {
        // print the instruction
        //I->print(llvm::outs());
        // llvm::outs() << '\n';

        // return the global variable
        return llvm::dyn_cast<llvm::GlobalVariable>(Iptr);
      }
    }
  }
  return nullptr;
}

// analyze all the ISRs and gathering the sets R and W
void analyzeISRs() {
  llvm::outs() << "\n//////Analysing ISRs//////\n";
  // go over every ISR
  for (auto &F : ISRs) {
    llvm::outs() << "\nanalysing ISR: '" << llvm::demangle(F->getName().str()) << "'\n";
    // go over every basic block in the function
    for (auto &BB : *F) {
      // go over every instruction in the basic block
      for (auto &I : BB) {
        // if its a read from a global variable instruction
        if (auto GV = getGlobalVariableRead(&I)){
          // insert into R
          R.insert(GV->getName().str());
          llvm::outs() << "\nAdded " << llvm::demangle(GV->getName().str()) << " to R\n";
        }
        // if its a write to a global variable instruction
        if (auto GV = getGlobalVariableWrite(&I)){
          // insert into W
          W.insert(GV->getName().str());
          llvm::outs() << "\nAdded " << llvm::demangle(GV->getName().str()) << " to W\n";
        }
      }
    }
  }
  return;
}

using namespace psr;

// define the domain of the analysis
struct MyAnalysisDomain : LLVMIFDSAnalysisDomainDefault {
  // using d_t = const llvm::Instruction *;
};

// define the IFDS analysis
class MyAnalysis : public IFDSTabulationProblem< MyAnalysisDomain > {
  public:
  MyAnalysis( const LLVMProjectIRDB *IRDB, std::vector<std::string> EntryPoints = {"main"} )
    : IFDSTabulationProblem(IRDB, std::move(EntryPoints), LLVMZeroValue::getInstance()) {}

  // define the normal flo function
  FlowFunctionPtrType getNormalFlowFunction(MyAnalysisDomain::n_t Curr, MyAnalysisDomain::n_t Succ) {
    // if its a read from a global variable instruction
    if (auto GV = getGlobalVariableRead(Curr)){
      auto GVname = GV->getName().str();
      // llvm::outs() << GV->getName().str() << " ISR R\n";
      // check if its present in W
      if (W.find(GVname) != W.end()) {
        // Curr->print(llvm::outs());
        output << llvm::demangle(GVname) << "\n";
        llvm::outs() << "\nRace Condition found at instruction: ";
        Curr->print(llvm::outs());
        llvm::outs() << "\n";
        // generate a new fact
        return generateFromZero(Curr);
      }
    }
    // if its a write to a global variable instruction
    if (auto GV = getGlobalVariableWrite(Curr)){
      auto GVname = GV->getName().str();
      // llvm::outs() << GV->getName().str() << " ISR W\n";
      // check if its present in W
      if (W.find(GVname) != W.end()) {
        // Curr->print(llvm::outs());
        output << llvm::demangle(GVname) << "\n";
        llvm::outs() << "\nRace condition found at instruction: ";
        Curr->print(llvm::outs());
        llvm::outs() << "\n";
        // generate a new fact
        return generateFromZero(Curr);
      }
      // check if its present in R
      if (R.find(GVname) != R.end()) {
        // Curr->print(llvm::outs());
        output << llvm::demangle(GVname) << "\n";
        llvm::outs() << "\nRace condition found at instruction: ";
        Curr->print(llvm::outs());
        llvm::outs() << "\n";
        // generate a new fact
        return generateFromZero(Curr);
      }
    }
    // otherwise
    return identityFlow();
  }

  // define the rest of the flow functions as identity functions
  
  FlowFunctionPtrType getCallFlowFunction(MyAnalysisDomain::n_t, MyAnalysisDomain::f_t) {
    return identityFlow();
  }

  FlowFunctionPtrType getRetFlowFunction(MyAnalysisDomain::n_t, MyAnalysisDomain::f_t, MyAnalysisDomain::n_t, MyAnalysisDomain::n_t) {
    return identityFlow();
  }

  FlowFunctionPtrType getCallToRetFlowFunction(MyAnalysisDomain::n_t, MyAnalysisDomain::n_t, llvm::ArrayRef<MyAnalysisDomain::f_t>) {
    return identityFlow();
  }

  InitialSeeds< MyAnalysisDomain::n_t, MyAnalysisDomain::d_t, MyAnalysisDomain::l_t > initialSeeds() {
    return createDefaultSeeds();
  }
};

int main(int Argc, const char **Argv) {
  using namespace std::string_literals;

  // check for correct usage
  if (Argc < 2 || !std::filesystem::exists(Argv[1]) ||
      std::filesystem::is_directory(Argv[1])) {
    llvm::errs() << "usage: <prog> <IR file>\n";
    return 1;
  }

  // parse the IR file into an LLVM module
  llvm::SMDiagnostic Diag;
  llvm::LLVMContext C;
  std::unique_ptr<llvm::Module> M = llvm::parseIRFile(Argv[1], Diag, C);

  // check if the module is alright
  bool broken_debug_info = false;
  if (M == nullptr ||
      llvm::verifyModule(*M, &llvm::errs(), &broken_debug_info)) {
    llvm::errs() << "error: module not valid\n";
    return 1;
  }
  if (broken_debug_info) {
    llvm::errs() << "caution: debug info is broken\n";
  }

  // find the ISRs
  findISRs(M);

  // add "main" into ISRs
  // auto F = M->getFunction("main");
  // if (!F) {
  //   llvm::errs() << "error: could not find function 'main'\n";
  //   return 1;
  // }
  // ISRs.insert(F);

  // analyze the ISRs
  analyzeISRs();

  // set the entry points of the analysis
  // std::vector EntryPoints = {"main"s}; // in case of standard c++ code
  std::vector EntryPoints = {"setup"s, "loop"s}; // in case of arduino code

  // define the helper analysis (used for creating an instance of our IFDS analysis)
  HelperAnalyses HA(Argv[1], EntryPoints);
  if (!HA.getProjectIRDB().isValid()) {
    return 1;
  }

  // create an instance of our IFDS analysis
  auto L = createAnalysisProblem<MyAnalysis>(HA, EntryPoints);

  // create an instance of the IFDS solver
  IFDSSolver S(L, &HA.getICFG());

  output << "Race Conditions:\n";
  llvm::outs() << "\n///////Running IFDS///////\n";

  // run the solver
  auto IFDSResults = S.solve();
  // display all the results in the IFDS analysis
  // IFDSResults.dumpResults(HA.getICFG());

  return 0;
}
