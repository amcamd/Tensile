import Structs
import SolutionWriter
import copy
import SolutionCandidateGenerator

class SolutionSelectionWriter:

  def __init__(self, psMap, backend):
    self.backend = backend
    self.solutionWriter = SolutionWriter.SolutionWriter(backend)
    self.psMap = psMap
    self.tolerance = 0.05
    self.kernelSet = set()
    self.solutionSet = set()
    #self.scg = SolutionCandidateGenerator.SolutionCandidateGenerator(False, False) # dummy generator for getting indices 0, 1
    self.printLogic = False
    self.fallbackPSPU1 = None
  
  def getKernelSet(self):
    return self.kernelSet

  def getSolutionSet(self):
    return self.solutionSet

  #############################################################################
  # write top level getSolution
  # chooses amongst devices
  #############################################################################
  def writeGetSolutionTop(self):
    functionName = "getSolutionTop"
    # source file
    s = ""
    s += "#include \"Problem.h\"\n"
    s += "#include \"CobaltGetSolution.h\"\n"
    for deviceProfile, exactMatches in self.psMap.iteritems():
      s += "#include \"CobaltGetSolution_" + deviceProfile.libString() + ".h\"\n"
    s += "\n"
    s += "Cobalt::Solution* " + functionName + "( const Cobalt::Problem & problem, CobaltStatus *status ) {\n"
    # if match device
    for deviceProfile, exactMatches in self.psMap.iteritems():
      s += "  if ( problem.deviceProfile.numDevices() == " + str(len(deviceProfile.devices)) + " ) {\n"
      s += "    if ( problem.deviceProfile[0].matches(\"" + deviceProfile.devices[0].name + "\")"
      for i in range(1, len(deviceProfile.devices)):
        s += " && problem.deviceProfile[" + str(i) + "].matches(\"" + deviceProfile.devices[i] + "\")"
      s += "   ) {\n"
      s += "      return getSolution_" + deviceProfile.libString() + "(problem, status);\n"
      s += "    }\n"
      s += "  }\n"
    # else doesn't match any device
    for deviceProfile, exactMatches in self.psMap.iteritems():
      s += "  /* doesn't match any known device; return a default */\n"
      s += "  return getSolution_" + deviceProfile.libString() + "(problem, status);\n"
      break
    if len(self.psMap) < 1:
      s += "  *status = cobaltStatusProblemNotSupported;\n"
      s += "  return nullptr;\n"
    s += "}\n"
    s += "\n"
    s += "void enumerateDeviceProfilesSupported( std::vector<CobaltDeviceProfile> & enumeratedProfiles ) {\n"
    s += "  CobaltDeviceProfile profile = cobaltCreateEmptyDeviceProfile();\n"
    s += "  profile.numDevices = 1;\n"
    for deviceProfile, exactMatches in self.psMap.iteritems():
      for device in deviceProfile.devices:
        s += "  sprintf(profile.devices[0].name, \"%s\");\n" % device.name
        s += "  profile.devices[0].numComputeUnits = %u;\n" % device.numComputeUnits
        s += "  profile.devices[0].clockFrequency = %u;\n" % device.clockFrequency
        s += "  enumeratedProfiles.push_back(profile);\n"
    s += "}\n"
    s += "\n"

    # header file
    h = ""
    h += "#ifndef COBALT_GETSOLUTION_H\n"
    h += "#define COBALT_GETSOLUTION_H\n"
    h += "\n"
    h += "#include \"Cobalt.h\"\n"
    h += "#include \"Solution.h\"\n"
    h += "\n"
    h += "Cobalt::Solution* " + functionName + "( const Cobalt::Problem & problem, CobaltStatus *status);\n"
    h += "\n"
    h += "void enumerateDeviceProfilesSupported( std::vector<CobaltDeviceProfile> & enumeratedProfiles );\n"
    h += "\n"
    h += "#endif\n"
    h += "\n"

    return (s, h)

  
  #############################################################################
  # write device-level getSolution
  # chooses amongst exact matches
  #############################################################################
  def writeGetSolutionForDevice( self, deviceProfile, exactMatches):
    functionName = "getSolution_" + deviceProfile.libString()
    s = ""
    s += "#include \"Problem.h\"\n"
    s += "#include \"CobaltGetSolution_" + deviceProfile.libString() + ".h\"\n"
    for exactMatch, problems in exactMatches.iteritems():
      s += "#include \"CobaltGetSolution_" + exactMatch.libString() + ".h\"\n"
    s += "\n"
    s += "Cobalt::Solution* " + functionName + "( const Cobalt::Problem & problem, CobaltStatus *status ) {\n"
    s += "  bool problemRequiresLeadingStrides = problem.tensorC[0].stride != 1 || problem.tensorA[0].stride != 1 || problem.tensorB[0].stride != 1;\n"
    s += "\n"
    
    for exactMatch, problems in exactMatches.iteritems():
      # if problem exactly matches EXACT_MATCH
      s += "  if ( problem.getDataTypeC() == " + exactMatch.typeC.getLibString() + "\n"
      s += "      && problem.getDataTypeA() == " + exactMatch.typeA.getLibString() + "\n"
      s += "      && problem.getDataTypeB() == " + exactMatch.typeB.getLibString() + "\n"
      s += "      && problem.getDataTypeAlpha() == " + exactMatch.typeAlpha.getLibString() + "\n"
      s += "      && problem.getDataTypeBeta() == " + exactMatch.typeBeta.getLibString() + "\n"
      s += "      && problem.operationType == " + exactMatch.operationType.getLibString() + "\n"
      s += "      && (!problem.useOffsets || problem.useOffsets == " + ("false" if exactMatch.ppdOffsets else "true") + ")\n"
      s += "      && (!problemRequiresLeadingStrides || problemRequiresLeadingStrides == " + ("false" if exactMatch.ppdLeadingStrides else "true") + ")\n"
      s += "      && problem.indicesFree.size() == " + str(exactMatch.numIndicesFree) + "\n"
      s += "      && problem.indicesA.size() == " + str(len(exactMatch.indexAssignmentsA)) + "\n"
      s += "      && problem.indicesB.size() == " + str(len(exactMatch.indexAssignmentsB)) + " ) {\n"
      
      s += "    if ("
      s += " problem.indicesA[0] == " + str(exactMatch.indexAssignmentsA[0]) + "\n"
      for i in range(1, len(exactMatch.indexAssignmentsA)):
        s += "        && problem.indicesA[" + str(i) + "] == " + str(exactMatch.indexAssignmentsA[i]) + "\n"
      s += "        && problem.indicesB[0] == " + str(exactMatch.indexAssignmentsB[0]) + "\n"
      for i in range(1, len(exactMatch.indexAssignmentsB)):
        s += "        && problem.indicesB[" + str(i) + "] == " + str(exactMatch.indexAssignmentsB[i])
        if i == len(exactMatch.indexAssignmentsB)-1:
          s += " ) {\n"
        else:
          s += "\n"

      s += "      return getSolution_" + exactMatch.libString() + "( problem, status);\n"
      s += "    }\n"
      s += "  }\n"
    
    s += "  *status = cobaltStatusProblemNotSupported;\n"
    s += "  return nullptr;\n"
    s += "}\n"
    s += "\n"
    
    # header file
    h = ""
    h += "#ifndef COBALT_" + functionName.upper() + "_H\n"
    h += "#define COBALT_" + functionName.upper() + "_H\n"
    h += "\n"
    h += "#include \"Cobalt.h\"\n"
    h += "#include \"Solution.h\"\n"
    h += "\n"
    h += "Cobalt::Solution* " + functionName + "( const Cobalt::Problem & problem, CobaltStatus *status);\n"
    h += "\n"
    h += "#endif\n"
    h += "\n"
    return (s, h)
  
  # fallback problem/solution pair = "b" solution or "m" solution which launched multiple kernels
  def isFallback(self, problem, solution):
    if solution.kernels[0].unrolls[len(solution.kernels[0].unrolls)-1] > 1:
      return False
    if solution.branch[0].isBranched() and solution.branch[1].isBranched():
      return True
    if solution.branch[0].isMultiple():
      problemSize0 = problem.tensorC.dimensions[solution.kernels[0].indexAssignmentDim0].size
      tileSize0 = solution.kernels[0].tile.workGroup[0] * solution.kernels[0].tile.microTile[0]
      if problemSize0 % tileSize0 > 0:
        return True
    if solution.branch[1].isMultiple():
      problemSize1 = problem.tensorC.dimensions[solution.kernels[0].indexAssignmentDim1].size
      tileSize1 = solution.kernels[0].tile.workGroup[1] * solution.kernels[0].tile.microTile[1]
      if problemSize1 % tileSize1 > 0:
        return True
    return False
  
  # single-kernel problem/solution pair = "b" solution or "m" solution which launched only one kernel
  def isSingleton(self, problem, solution):
    if solution.branch[0].isMultiple():
      problemSize0 = problem.tensorC.dimensions[solution.kernels[0].indexAssignmentDim0].size
      tileSize0 = solution.kernels[0].tile.workGroup[0] * solution.kernels[0].tile.microTile[0]
      if problemSize0 % tileSize0 > 0:
        return False
    if solution.branch[1].isMultiple():
      problemSize1 = problem.tensorC.dimensions[solution.kernels[0].indexAssignmentDim1].size
      tileSize1 = solution.kernels[0].tile.workGroup[1] * solution.kernels[0].tile.microTile[1]
      if problemSize1 % tileSize1 > 0:
        return False
    return True

  
  # size of free indices, i.e., how many threads
  # def getSize(self, problem):
  #   totalSize = 1
  #   # multiply free indices
  #   for dimension in problem.tensorC.dimensions:
  #     totalSize *= dimension.size
  #   return totalSize

  def getGFlops(self, problem, timeMS):
    totalFlops = problem.getSizeFree()
    if problem.tensorA.dataType.isReal():
      totalFlops *= 2
    else:
      totalFlops *= 8
    ## multiply summation indices
    for i in range(0, len(problem.operation.indexAssignmentsA)):
      index = problem.operation.indexAssignmentsA[i]
      inC = index < len(problem.tensorC.dimensions)
      inB = index in problem.operation.indexAssignmentsB
      if inB and not inC: # is summation dimension
        totalFlops *= problem.tensorA.dimensions[i].size
        
    gFlops = (totalFlops/1000000000.0) / (timeMS/1000.0)
    return gFlops
        
  def getGFlopsString(self, problem, timeMS):
    s = ""
    totalFlops = 1
    if problem.tensorA.dataType.isReal():
      totalFlops *= 2
      s += "2"
    else:
      totalFlops *= 8
      s += "8"
    # free indices
    for dimension in problem.tensorC.dimensions:
      totalFlops *= dimension.size
      s += "*" + str(dimension.size)
    # multiply summation indices
    for i in range(0, len(problem.operation.indexAssignmentsA)):
      index = problem.operation.indexAssignmentsA[i]
      inC = index < len(problem.tensorC.dimensions)
      inB = index in problem.operation.indexAssignmentsB
      if inB and not inC: # is summation dimension
        totalFlops *= problem.tensorA.dimensions[i].size
        s += "*" + str(problem.tensorA.dimensions[i].size)

    gFlops = (totalFlops/1000000000.0) / (timeMS/1000.0)
    s += " ops / %.3fms = %.0f GFlop/s" % (timeMS, gFlops)
    return s


  def getFallbacks(self, psps):
    fallbacks = []
    for i in range(0, len(psps)):
      problem = psps[i][0]
      solution = psps[i][1]
      if self.isFallback(problem, solution):
        fallbacks.append( psps[i] )
    return fallbacks
  
  def getSingletons(self, psps):
    singles = []
    for i in range(0, len(psps)):
      problem = psps[i][0]
      solution = psps[i][1]
      if self.isSingleton(problem, solution):
        singles.append( psps[i] )
    return singles

  def getIndexOfFastest( self, psps ):
    fastestIndex = 0
    fastestProblem = psps[fastestIndex][0]
    fastestSolution = psps[fastestIndex][1]
    fastestTime = psps[fastestIndex][2]
    fastestGFlops = self.getGFlops(fastestProblem, fastestTime)
    for i in range(1, len(psps)):
      if self.getGFlops(psps[i][0], psps[i][2]) > fastestGFlops:
        fastestIndex = i
        fastestProblem = psps[fastestIndex][0]
        fastestSolution = psps[fastestIndex][1]
        fastestTime = psps[fastestIndex][2]
        fastestGFlops = self.getGFlops(fastestProblem, fastestTime)
    return fastestIndex

  def getIndexOfLargest( self, psps ):
    largestIndex = 0
    largestProblem = psps[largestIndex][0]
    largestSize = largestProblem.getSizeFree()
    for i in range(1, len(psps)):
      if psps[i][0].getSizeFree() > largestSize:
        largestIndex = i
        largestProblem = psps[largestIndex][0]
        largestSize = largestProblem.getSizeFree()
    return largestIndex


  def sortSizePSPs( self, inputPSPs ):
    # can't get this to work
    # sorted(inputPSPs, key=lambda psp: psp[0].getSizeFree() )
    # return inputPSPs

    psps = inputPSPs # copy.deepcopy(inputPSPs)
    s = []
    while len(psps) > 0:
      indexOfLargest = self.getIndexOfLargest(psps)
      #print "indexOfLargest = %u (%u)" % (indexOfLargest, psps[indexOfLargest][0].getSizeFree())
      s.append( psps.pop(indexOfLargest) )
    return s

  def sortSpeedPSPs( self, inputPSPs ):
    psps = inputPSPs # copy.deepcopy(inputPSPs)
    s = []
    while len(psps) > 0:
      indexOfFastest = self.getIndexOfFastest(psps)
      s.append( psps.pop(indexOfFastest) )
    return s

  def getPSPsWithSize(self, psps, size ):
    s = []
    s[:] = [ psp for psp in psps if psp[0].getSizeFree() == size ]
    # for psp in psps:
    #   self.sizeOfPSP = psp[0].getSizeFree()
    #   if self.sizeOfPSP == size:
    #     s.append(psp)
    return s

  def getIndexOfSolution( self, psps, solution ):
    for i in range(0, len(psps)):
      if psps[i][1] == solution:
        return i
    return len(psps)

  # returns a problem with largest size
  def getLargestSize(self, psps):
    largestSize = 0;
    largestProblem = psps[largestSize][0]
    for psp in psps:
      size = psp[0].getSizeFree()
      if size > largestSize:
        largestSize = size
        largestProblem = psp[0]
    return largestProblem

  #  1 if p0 > p1
  # -1 is p0 < p1
  #  0 if equal
  def compareSize(self, p0, p1):
    # check free indices
    for i in range( 0, len(p0.tensorC.dimensions)):
      # print "comparing free index %u / %u" %( i, len(p0.tensorC.dimensions) )
      size0 = p0.tensorC.dimensions[i].size
      size1 = p1.tensorC.dimensions[i].size
      if size0 - size1 > 1:
        return 1
      elif size0 - size1 < -1:
        return -1
    # check summation indices
    for i in range(0, len(p0.operation.indexAssignmentsA)):
      # print "comparing summation index " + str(i)
      index = p0.operation.indexAssignmentsA[i]
      inC = index < len(p0.tensorC.dimensions)
      inB = index in p0.operation.indexAssignmentsB
      if inB and not inC: # is summation dimension
        size0 = p0.tensorA.dimensions[i].size
        size1 = p1.tensorA.dimensions[i].size
        if size0 - size1 > 1:
          return 1
        elif size0 - size1 < -1:
          return -1
    return 0


  def getPSPsForSize( self, psps, sizeP):
    s = []
    for i in range(0, len(psps)):
      psp = psps[i]
      # print "checking if size of psps[%u] matches %u" % (i, self.getSize(sizeP)**(1.0/2.0))
      if self.compareSize(psp[0], sizeP) == 0:
        #print "appending psp for size %u" % self.getSize(sizeP)**(1.0/2.0)
        s.append(psp)
    #print "returning getPSPsForSize"
    return s

  def getPSPsLargerOrEqual( self, psps, sizeP):
    s = []
    for i in range(0, len(psps)):
      psp = psps[i]
      # print "checking if size of psps[%u] matches %u" % (i, self.getSize(sizeP)**(1.0/2.0))
      if self.compareSize(psp[0], sizeP) >= 0:
        #print "appending psp for size %u" % self.getSize(sizeP)**(1.0/2.0)
        s.append(psp)
    #print "returning getPSPsForSize"
    return s

  # psp must be faster than fasterThan and not duplicate prior
  def getPSPsFasterThan(self, psps, fasterThan):
    fastProblem = fasterThan[0]
    fastSolution = fasterThan[1]
    fastTime = fasterThan[2]
    fastSize = fastProblem.getSizeFree()
    fastGFlops = self.getGFlops(fastProblem, fastTime)
    s = []
    for psp in psps:
      if self.getGFlops(psp[0], psp[2]) > fastGFlops:
        # make sure it isn't a duplicate
        s.append(psp)
        #print "%s faster than %s" % (self.pspToString(psp), self.pspToString(fasterThan))
      #else:
        #print "%s slower than %s" % (self.pspToString(psp), self.pspToString(fasterThan))
    return s

  def removeTileDuplicates(self, psps):
    s = []
    for newPSP in psps:
      tileAlreadyCovered = False
      for alreadyPSP in s:
        if self.coversSameDim(alreadyPSP[1], newPSP[1]):
          tileAlreadyCovered = True
      if not tileAlreadyCovered:
        s.append(newPSP)
    return s


  def pspToString(self, psp):
    return "%s - %s-----%s" % ( self.getGFlopsString(psp[0], psp[2]), str(psp[0]), self.solutionWriter.getName(psp[1]) )

  def ruleToString(self, rule):
    s = "size = "
    # lower bound
    if rule[3] != None:
      sizeLower = rule[3].getSizeFree()**(1.0/2.0)
      s += str(sizeLower)
    else:
      s += "-1"
    s += " -> "
    # upper bound
    if rule[2] != None:
      sizeUpper = rule[2].getSizeFree()**(1.0/2.0)
      s += str(sizeUpper)
    else:
      s += "inf"
    s += "\n"
    # unordered groups
    unorderedGroups = rule[0]
    sizeLower = rule[3].getSizeFree()**(1.0/2.0)
    for group in unorderedGroups:
      for psp in group:
        s += "  " + self.pspToString(psp)
      s += "\n"
    
    # fallback  
    fallback = rule[1]
    s += "fb" + self.pspToString(fallback)
    return s
    

  def getIndexOfNextLargestSize(self, psps, sizeP):
    for i in range(0, len(psps)):
      #print "checking if %u/%u is next largest size" % ( i, len(psps))
      currentSizeP = psps[i][0]
      if self.compareSize(currentSizeP, sizeP) < 0:
        #print "next largest size at index " + str(i)
        return i
    #print "no next largest size"
    return len(psps)

  def removePSPsLargerOrEqual(self, psps, sizeP ):

    psps[:] = [ psp for psp in psps if self.compareSize(psp[0], sizeP) < 0 ]

    #size = self.getSize(sizeP)**0.5
    #print "STATUS - removing psps larger than %u*%u" % (size, size)
    #index = 0
    #for psp in psps:
    #  pspSize = self.getSize(psp[0])**0.5
    #  pspName = self.solutionWriter.getName(psp[1])
    #  if self.compareSize(psp[0], sizeP) > -1:
    #    psps.remove(psp)
    #    print "removing %u b/c size %u*%u - %s" % (index, pspSize, pspSize, pspName)
    #  else:
    #    print "NOT removing %u b/c size %u*%u - %s" % (index, pspSize, pspSize, pspName)
    #  index += 1


  # are the dims covered by s1 already covered by s0
  def coversSameDim01( self, s0, s1 ):
    mt_s0_d0 = s0.kernels[0].tile.workGroup[0] * s0.kernels[0].tile.microTile[0]
    mt_s0_d1 = s0.kernels[0].tile.workGroup[1] * s0.kernels[0].tile.microTile[1]
    mt_s1_d0 = s1.kernels[0].tile.workGroup[0] * s1.kernels[0].tile.microTile[0]
    mt_s1_d1 = s1.kernels[0].tile.workGroup[1] * s1.kernels[0].tile.microTile[1]

    if mt_s1_d0 % mt_s0_d0 > 0:
      return False
    if mt_s1_d1 % mt_s0_d1 > 0:
      return False
    return True

  def coversSameDim( self, s0, s1 ):
    mt_s0_d0 = s0.kernels[0].tile.workGroup[0] * s0.kernels[0].tile.microTile[0]
    mt_s0_d1 = s0.kernels[0].tile.workGroup[1] * s0.kernels[0].tile.microTile[1]
    mt_s0_dU = s0.kernels[0].unrolls[len(s0.kernels[0].unrolls)-1]
    mt_s1_d0 = s1.kernels[0].tile.workGroup[0] * s1.kernels[0].tile.microTile[0]
    mt_s1_d1 = s1.kernels[0].tile.workGroup[1] * s1.kernels[0].tile.microTile[1]
    mt_s1_dU = s1.kernels[0].unrolls[len(s1.kernels[0].unrolls)-1]

    if mt_s1_d0 % mt_s0_d0 > 0:
      return False
    if mt_s1_d1 % mt_s0_d1 > 0:
      return False
    if mt_s1_dU % mt_s0_dU > 0:
      return False

    return True

  # two rules conflict only if they have same elements in different order
  def rulesConflict(self, rule, newRule):
    #print "checking if rules conflict"
    unorderedGroups = rule[0]
    unorderedGroupsNew = newRule[0]

    # check if solution for tile conflicts
    for ug in unorderedGroups:
      for nug in unorderedGroupsNew:
        for psp in ug:
          for npsp in nug:
            # if psp and npsp have exactly same tile but are different solution, then conflict
            if self.coversSameDim( psp[1], npsp[1]) and self.coversSameDim( npsp[1], psp[1]):
              if not psp[1] == npsp[1]:
                #print "psp " + self.pspToString(psp) + " conflicts with npsp " + self.pspToString(npsp)
                return True


    # check if solution order conflicts
    unorderedGroups = rule[0]
    unorderedGroupsNew = newRule[0]
    for i in range(0,len(unorderedGroups)):
      #print i
      unorderedGroup = unorderedGroups[i]
      for j in range(i+1, len(unorderedGroups)):
        #print i, j
        unorderedGroupSubsequent = unorderedGroups[j]
        #rule says all elements in ordered unit are faster than all elements in subsequent ordered unit
        for iNew in range(0,len(unorderedGroupsNew)):
          #print i, j, iNew
          unorderedGroupNew = unorderedGroupsNew[iNew]
          for jNew in range(iNew+1, len(unorderedGroupsNew)):
            #print i, j, iNew, jNew
            unorderedGroupNewSubsequent = unorderedGroupsNew[jNew]
            #new rule says all elements in ordered unit are faster than all elements in subsequent ordered unit
            for pspi in range(0,len(unorderedGroup)):
              #print i, j, iNew, jNew, pspi
              psp = unorderedGroup[pspi]
              solution = psp[1]
              solutionInNewRuleSubsequent = False
              for pspNewi in range(0, len(unorderedGroupNewSubsequent)):
                #print i, j, iNew, jNew, pspi, pspNewi
                pspNew = unorderedGroupNewSubsequent[pspNewi]
                if self.coversSameDim( pspNew[1], solution):
                  solutionInNewRuleSubsequent = True
                  break
              if solutionInNewRuleSubsequent:
                for pspSubsequent in unorderedGroupSubsequent:
                  solutionSubsequent = pspSubsequent[1]
                  solutionSubsequentInNewRule = False # if stile in ordered unit in new rule
                  for pspNew in unorderedGroupNew:
                    if self.coversSameDim(pspNew[1], solutionSubsequent):
                      solutionSubsequentInNewRule = True
                      break
                    #else:
                      #print "solutions not equal"
                  if solutionSubsequentInNewRule:
                    #print "rule conflict detected"
                    return True
    #print "no rule conflict detected"
    return False


  def mergeRules(self, rule, inputNewRule):
    newRule = copy.deepcopy(inputNewRule)
    # already determined no conflicts
    # order only determined when multiple tiles show up in same problem size
    ugs = copy.deepcopy(rule[0]) # unordered groups
    nugs = copy.deepcopy(newRule[0]) # new unordered groups
    mugs = [] # merged unordered groups

    ugi = 0 # unordered group idx
    nugi = 0 # new unordered group idx
    #mugi = 0 # merged unordered group idx


    while ugi < len(ugs) or nugi < len(nugs):
      PSPsValid = []
      if ugi < len(ugs):
        for psp in ugs[ugi]:
          PSPsValid.append(psp)
          #print "appending to pspsValid " + self.pspToString(psp)

        # eliminate ones in nugs[nugi+1+]
        for psp in PSPsValid:
          invalid = False
          for j in range( nugi+1, len(nugs)):
            nug = nugs[j]
            for npsp in nug:
              if self.coversSameDim( npsp[1], psp[1]) and self.coversSameDim( psp[1], npsp[1]):
                #print "invalidating pspsValid " + self.pspToString(psp) + " b/c " + self.pspToString(npsp)
                # remove this from PSPsValid
                invalid = True
          if invalid:
            PSPsValid.remove(psp)
      #print "getting npsps valid"
      nPSPsValid = []
      if nugi < len(nugs):
        for npsp in nugs[nugi]:
          nPSPsValid.append(npsp)
          #print "appending to npspsValid " + self.pspToString(npsp)
        # eliminate ones in ugs[ugi+1+]
        for npsp in nPSPsValid:
          invalid = False
          for j in range( ugi+1, len(ugs)):
            ug = ugs[j]
            for psp in ug:
              if self.coversSameDim( psp[1], npsp[1]) and self.coversSameDim( npsp[1], psp[1]):
                #print "invalidating npspsValid " + self.pspToString(npsp) + " b/c " + self.pspToString(npsp)
                # remove this from nPSPsValid
                invalid = True
          if invalid:
            nPSPsValid.remove(npsp)
      #print "merging psps"
      # merge ugs
      mPSPsValid = []
      for psp in PSPsValid:
        mPSPsValid.append(psp)
      for psp in nPSPsValid:
        # is solution already in list
        hasPSP = False
        #print "checking if psp already in merged ug"
        for otherPSP in mPSPsValid:
          if otherPSP[1] == psp[1]:
            hasPSP = True
            break
        if not hasPSP:
          mPSPsValid.append(psp)
      mugs.append(mPSPsValid)
      #print "removing currently used ugs from list of remaining lists"
      if ugi < len(ugs):
        # remove PSPsValid from ugs[ugi]
        for psp in PSPsValid:
          #print "removing psp from ugs[%u] len=%u" % (ugi, len(ugs[ugi]))
          ugs[ugi].remove(psp)
          #print "removed  psp from ugs[%u] len=%u" % (ugi, len(ugs[ugi]))
        if len(ugs[ugi]) == 0:
          ugi+=1
      if nugi < len(nugs):
        # remove nugsValid from nugs[nugi]
        for npsp in nPSPsValid:
          #print "removing npsp from nugs[%u] len=%u" % (nugi, len(nugs[nugi]))
          nugs[nugi].remove(npsp)
          #print "removed  npsp from nugs[%u] len=%u" % (nugi, len(nugs[nugi]))
        if len(nugs[nugi]) == 0:
          nugi+=1

    # update rule with new unorderedGroups
    #print "updating rule with merged ugs"
    rule[0] = mugs # self.removeTileDuplicates( mugs )

    # update rule with new upper limit
    #print "updating rule with merged upper limit"
    if rule[2] != None:
      if newRule[2] != None:
        if self.compareSize(newRule[2], rule[2]) > 0:
          rule[2] = newRule[2]
        else:
          pass # original rule already higher upper bound
      else:
        rule[2] = None # merged rule infinite upper bound
    else:
      pass # original rule already infinite upper bound

    # update rule with new lower limit
    #print "updating rule with merged upper limit"
    if rule[3] != None:
      if newRule[3] != None:
        if self.compareSize(newRule[3], rule[3]) < 0:
          rule[3] = newRule[3]
        else:
          pass # original rule already lower lower bound
      else:
        rule[3] = None # merged rule zero lower bound
    else:
      pass # original rule already zero lower bound

    return

  def addPSPToSets( self, psp):
    #startSolutionSetSize = len(self.solutionSet)
    #startKernelSetSize = len(self.kernelSet)
    self.solutionSet.add( psp[1] )
    #print "addPSPToSets() %i->%i add-s %s" % (startSolutionSetSize, len(self.solutionSet), str(psp[1]))
    for kernel in psp[1].kernels:
      if kernel != None:
        self.kernelSet.add( kernel )
        #print "addPSPToSets() %i->%i add-k %s" % (startKernelSetSize, len(self.kernelSet), str(kernel))

  def addRuleToSets(self, rule):
    for ug in rule[0]: # exact tiles
      for psp in ug:
        self.addPSPToSets(psp)
    self.addPSPToSets(rule[1]) # fallback
    #newFallbackPSP = copy.deepcopy( rule[1] )
    #for i in range( 0, 4):
    #  if newFallbackPSP[1].kernels[i] != None:
    #    newFallbackPSP[1].kernels[i].unrolls = [ 1 ]
    #self.addPSPToSets(newFallbackPSP)


  def ruleToLibString(self, rule, firstSizeGroup, lastSizeGroup, exactPSPsInRange, indent):
    s = ""
    if firstSizeGroup:
      s += "  if ("
    elif lastSizeGroup:
      s += " else "
    else:
      s += " else if ("
    if firstSizeGroup and lastSizeGroup:
        s += " true ||"
    if firstSizeGroup or not lastSizeGroup:
      if rule[2] != None:
        thresholdUpper = int( rule[2].getSizeFree()**(1.0/2.0) )
        s += " sizeFree < %5u*%5u" % (thresholdUpper, thresholdUpper)
      if rule[2] != None and rule[3] != None:
        s += " && "
      if rule[3] != None:
        thresholdLower = int( rule[3].getSizeFree()**(1.0/2.0) )
        s += " sizeFree >= %5u*%5u" % (thresholdLower, thresholdLower)
      s += " ) "
    s += "{\n"

    # select exact-size-problems based on exact size
    for exactPSP in exactPSPsInRange:
      problem = exactPSP[0]
      solution = exactPSP[1]
      size0 = problem.tensorC.dimensions[solution.kernels[0].indexAssignmentDim0].size
      size1 = problem.tensorC.dimensions[solution.kernels[0].indexAssignmentDim1].size
      unrollIndex = solution.kernels[0].indexOrderSummation[ len(solution.kernels[0].indexOrderSummation)-1] + len(solution.kernels[0].indexOrderC)
      sizeU = -1
      for i in range(0,len(problem.operation.indexAssignmentsA)):
        index = problem.operation.indexAssignmentsA[i]
        if index == unrollIndex:
          sizeU = problem.tensorA.dimensions[i].size
      gflops = self.getGFlopsString(exactPSP[0], exactPSP[2])
      s += indent + "  if ( size0 == %3u && size1 == %3u && sizeU == %2u ) {" % (size0, size1, sizeU)
      s += " return new Cobalt::%s%s( problem ); } // %s\n" %( self.solutionWriter.getName(solution), self.solutionWriter.getTemplateArgList(solution), gflops )
          

    # select range-size-problems based on multiples
    uniques = [] # avoid redundants
    for ug in rule[0]:
      for modPSP in ug:
        tileAlreadyCovered = False
        for alreadyPSP in uniques:
          if self.coversSameDim(alreadyPSP[1], modPSP[1]):
            tileAlreadyCovered = True
        if not tileAlreadyCovered:
          solution = modPSP[1]
          size0 = solution.kernels[0].tile.workGroup[0] * solution.kernels[0].tile.microTile[0]
          size1 = solution.kernels[0].tile.workGroup[1] * solution.kernels[0].tile.microTile[1]
          sizeU = solution.kernels[0].unrolls[len(solution.kernels[0].unrolls)-1]
          sizeUL = 0
          for unroll in solution.kernels[0].unrolls:
            sizeUL += unroll
          gflops = self.getGFlopsString(modPSP[0], modPSP[2])
          s += indent + "  if ( size0 %% %3u == 0 && size1 %% %3u == 0 && sizeU %% %2u == 0 && sizeU >= %2u) {" % (size0, size1, sizeU, sizeUL)
          s += " return new Cobalt::%s%s( problem ); } // %s\n" %( self.solutionWriter.getName(solution), self.solutionWriter.getTemplateArgList(solution), gflops )
          uniques.append(modPSP)
    fallbackPSP = rule[1]
    if fallbackPSP != None:
      fallbackSolution = fallbackPSP[1]
      sizeUL = fallbackSolution.kernels[0].unrolls[0]
      gflops = self.getGFlopsString(fallbackPSP[0], fallbackPSP[2])
      s += indent + "  if ( sizeU >= %2u) { return new Cobalt::%s%s( problem ); } // %s\n" % (sizeUL, self.solutionWriter.getName(fallbackSolution), self.solutionWriter.getTemplateArgList(fallbackSolution), gflops)
      #newFallbackSolution = copy.deepcopy( fallbackSolution )
      #for i in range( 0, 4):
      #  if newFallbackSolution.kernels[i] != None:
      #    newFallbackSolution.kernels[i].unrolls = [ 1 ]
      #s += indent + "  return new Cobalt::%s%s( problem );\n" % (self.solutionWriter.getName(newFallbackSolution), self.solutionWriter.getTemplateArgList(newFallbackSolution))
    else:
      s += indent + "  *status = cobaltStatusProblemNotSupported; // backend written with only exact solutions, and this problem not explicitly supported\n"
      s += indent + "  return nullptr;\n"
    s += indent + "}"
    return s


  #############################################################################
  # write exact match level getSolution
  # chooses amongst sizes and mods
  #############################################################################
  def writeGetSolutionForExactMatch(self, exactMatch, \
      inputRangePSPs, inputExactPSPs):
    s = ""
    h = ""
    fastestPSPs = set()
    if len(inputRangePSPs) < 1 and len(inputExactPSPs) < 1:
      return (s, h, fastestPSPs)
    exactOnly = len(inputRangePSPs)==0
    print "writeGetSolutionForExactMatch(%s;%i;%i)" % (str(exactMatch), len(inputRangePSPs), len(inputExactPSPs))

    #print "Sorting %u rangePSPs, %u exactPSPs" % (len(inputRangePSPs), len(inputExactPSPs))
    rangePSPs = self.sortSizePSPs(inputRangePSPs)
    exactPSPs = self.sortSizePSPs(inputExactPSPs)
    #print "Sorting done."
    
    # index = 0
    # for psp in rangePSPs:
    #   size = psp[0].getSizeFree()**0.5
    #   name = self.solutionWriter.getName(psp[1])
    #   print "(%4u) %4ux%4u - %s" % (index, size, size, name)
    #   index += 1
    
    localSolutionSet = set() # for solution header includes
    kernel = Structs.Kernel()
    if exactOnly:
      problem = exactPSPs[0][0]
    else:
      problem = rangePSPs[0][0]
    SolutionCandidateGenerator.makeIndexAssignments(kernel, problem)
    # sort psps by descending size
    functionName = "getSolution_" + exactMatch.libString()


    s += "Cobalt::Solution* " + functionName + "( const Cobalt::Problem & problem, CobaltStatus *status ) {\n"
    s += "  size_t sizeFree = problem.tensorC.numElements(); // size0*size1*size of other free indices\n"
    s += "  unsigned int size0 = problem.tensorC[%u].size;\n" % (kernel.indexAssignmentDim0)
    s += "  unsigned int size1 = problem.tensorC[%u].size;\n" % (kernel.indexAssignmentDim1)
    #print "indexOrderSummation", kernel.indexOrderSummation
    dimU = len(problem.tensorC.dimensions) + kernel.indexOrderSummation[len(kernel.indexOrderSummation)-1]
    #print "dimU", dimU
    idxU = -1
    #print "indexAssignmentsA", problem.operation.indexAssignmentsA
    for i in range(0, len(problem.operation.indexAssignmentsA)):
      if problem.operation.indexAssignmentsA[i] == dimU:
        idxU = i
    s += "  unsigned int sizeU = problem.tensorA[%u].size;\n" % (idxU)
    s += "  *status = cobaltStatusSuccess; // if you made it this far, you're likely guaranteed a correct solution\n"

    firstSizeGroup = True
    lastSizeGroup = False
    if exactOnly:
      #print "SSL for Unique Problems only."
      firstSizeGroup = True
      lastSizeGroup = True
      # create single rule for size zero
      unorderedGroups = []
      fallback = None # exactPSPs[0]
      ruleSizeThresholdUpperP = None
      fallbackLowerBoundP = exactPSPs[0][0]
      rule = [unorderedGroups, fallback, ruleSizeThresholdUpperP, fallbackLowerBoundP]
      #ruleString = self.ruleToString(rule)
      #print "RULE: " + ruleString
      
      exactPSPsInRange = exactPSPs
      fastestExactPSPsInRange = []
      # for each unique problem, get only fastest
      iterCnt = 0
      #print "total = %u exact psps" % len(exactPSPsInRange)
      while len(exactPSPsInRange) > 0:
        iterCnt += 1
        if iterCnt > 20:
          break
        #print "new problem"
        problem = exactPSPsInRange[0][0]
        fastestTime  = 1e9
        fastestIndex = -1
        slowPSPs = []

        for i in range(0, len(exactPSPsInRange)):
          psp = exactPSPsInRange[i]
          if psp[0] == problem:
            time = psp[2]
            if time < fastestTime:
              #print "new fastest solution"
              fastestTime = time
              if fastestIndex >= 0:
                slowPSPs.append(exactPSPsInRange[fastestIndex])
              fastestIndex = i
            else:
              slowPSPs.append(psp)
          #else:
            #print "problem not match"
        #print "%u slow psps" % len(slowPSPs)
        fastestExactPSPsInRange.append(exactPSPsInRange[fastestIndex])
        exactPSPsInRange.remove(exactPSPsInRange[fastestIndex])
        for slowPSP in slowPSPs:
          exactPSPsInRange.remove(slowPSP)
      for psp in fastestExactPSPsInRange:
        #print "adding " + str(psp[1])
        localSolutionSet.add( psp[1] )
        #print "writeGetSolutionForExactMatch(%s) adding %s" % (str(exactMatch), str(psp))
        self.addPSPToSets(psp)
        #print self.pspToString(fallback) + " - adding exacts only"
        fastestPSPs.add( tuple(copy.deepcopy(psp)) )

      # self.addRuleToSets(rule)
      s += self.ruleToLibString(rule, firstSizeGroup, lastSizeGroup, fastestExactPSPsInRange, "  ")
          
    else:
      # determine fastest branched fallback to use for unroll=1
      fastestIdxU1 = -1
      fastestGFlopsU1 = -1
      for i in range(0,len(rangePSPs)):
        psp = rangePSPs[i]
        if psp[1].branch[0].isBranched():
          gflops = self.getGFlops(psp[0], psp[2])
          if gflops > fastestGFlopsU1:
            fastestIdxU1 = i
            fastestGFlopsU1 = gflops
      self.fallbackPSPU1 = copy.deepcopy(rangePSPs[fastestIdxU1])
      self.fallbackPSPU1[1].kernels[0].unrolls = [ 1 ]
      self.addPSPToSets(self.fallbackPSPU1)
      localSolutionSet.add(self.fallbackPSPU1[1])
      while len(rangePSPs) > 0:
        if self.printLogic: print "STATUS - psps remaining = " + str(len(rangePSPs))

        #########################################################################
        # (a) determine fastest fallback psp at largest size
        #########################################################################
        ruleSizeThresholdUpperP = None
        largestSizeP = self.getLargestSize(rangePSPs)
        size = largestSizeP.getSizeFree()**0.5
        if self.printLogic: print "STATUS - creating rule for size %u*%u" % (size, size)
        pspsForLargestSize = self.getPSPsForSize(rangePSPs, largestSizeP)
        fallbacksForLargestSize = self.getFallbacks(pspsForLargestSize)
        while len(fallbacksForLargestSize) < 1:
          size = largestSizeP.getSizeFree()**(1.0/2.0)
          if size%16 == 0:
            if self.printLogic: print "WARNING - not fallbacks for size " + str(size)
          indexOfNextLargestSize = self.getIndexOfNextLargestSize(rangePSPs, largestSizeP)
          if indexOfNextLargestSize == len(rangePSPs):
            # no next smallest size
            # no fallbacks
            break
          nextLargestSizeP = rangePSPs[indexOfNextLargestSize][0]
          pspsForNextLargestSize = self.getPSPsForSize(rangePSPs, nextLargestSizeP)
          fallbacksForLargestSize = self.getFallbacks(pspsForNextLargestSize)

        # if no fallbacks benchmarked, pick any and make its time slowest
        fallbackExists = len(fallbacksForLargestSize) > 0
        if not fallbackExists:
          if self.printLogic: print "WARNING - no fallbacks exist for any size"
          fallbacksForLargestSize.append(rangePSPs[0])
          fallbacksForLargestSize[0][2] = 1e10
        indexOfFastestFallback = self.getIndexOfFastest( fallbacksForLargestSize )
        fallback = fallbacksForLargestSize[indexOfFastestFallback]
        fallbackProblem = fallback[0]
        fallbackSolution = fallback[1]
        fallbackTime = fallback[2]
        #print self.pspToString(fallback) + " - adding fallback"
        fastestPSPs.add( tuple(copy.deepcopy(fallback)) )
        fallbackGFlops = self.getGFlops(fallbackProblem, fallbackTime)
        size = fallbackProblem.getSizeFree()**0.5
        pspString = self.pspToString(fallback)
        if self.printLogic: print "STATUS - fastest fallback for size %u*%u is %s" % (size, size, pspString)

        #########################################################################
        # (b) going from largest problem to smallest problem,
        # find smallest size for which the fastest fallback solution
        # at the problem size is still the fastest fallback solution
        #########################################################################
        fallbackLowerBoundP = fallbackProblem
        if fallbackExists:
          fallbacks = self.getFallbacks(rangePSPs)
          # for fallback in fallbacks:
          #   fs = self.pspToString(fallback)
          #   print "FALLBACK = " + fs
          fallbackSizeThreshold = fallbackProblem.getSizeFree()
          currentFallback = None
          for i in range(0, len(fallbacks)):
            currentSize = fallbacks[i][0].getSizeFree()
            if currentSize < fallbackSizeThreshold:
              # get speed of original fallback at current size
              fallbacksForSize = self.getPSPsWithSize( fallbacks, currentSize)
              indexOfFallbackForSize = self.getIndexOfSolution(fallbacksForSize, fallbackSolution)
              if indexOfFallbackForSize >= len(fallbacksForSize):
                if self.printLogic: print "WARNING - fallback wasn't benchmarked at size %u*%u" % (currentSize**0.5, currentSize**0.5)
                # fallback wasn't tested at this size
                continue
              # original fallback solution benchmarked at current problem size
              fallbackForSize = fallbacksForSize[indexOfFallbackForSize]
              fastestPSPs.add( tuple(copy.deepcopy(fallbackForSize)) )
              fallbackProblemForSize = fallbackForSize[0]
              fallbackSolutionForSize = fallbackForSize[1]
              fallbackTimeForSize = fallbackForSize[2]
              fallbackGFlopsForSize = self.getGFlops( fallbackProblemForSize, fallbackTimeForSize)
              # fastest fallback solution benchmarked at current problem size
              indexOfFastestFallbackForSize = self.getIndexOfFastest(fallbacksForSize)
              currentFallback = fallbacksForSize[indexOfFastestFallbackForSize]
              #print self.pspToString(currentFallback) + " - adding same fallback at smaller size"
              fastestPSPs.add( tuple(copy.deepcopy(currentFallback)) )
              currentProblem = currentFallback[0]
              currentSolution = currentFallback[1]
              currentTime = currentFallback[2]
              currentGFlops = self.getGFlops(currentProblem, currentTime)
              if not currentSolution == fallbackSolutionForSize:
                if currentGFlops > fallbackGFlopsForSize*(1+self.tolerance):
                  # starting with current size, there's a new fastest fallback
                  if self.printLogic: print "STATUS - at size %u*%u new fastest fallback is %s" % (currentSize**0.5, currentSize**0.5, self.solutionWriter.getName(currentSolution))
                  if self.printLogic: print "  forSize = " + self.solutionWriter.getName(fallbackSolutionForSize)
                  if self.printLogic: print "  fallback= " + self.solutionWriter.getName(currentSolution)
                  break
                else:
                  # new fallback is faster but still within tolerance
                  if self.printLogic: print "STATUS - fallback is fastest at size %u*%u too (by threshold)" % (currentSize**0.5, currentSize**0.5)
                  #fallbackSizeThreshold = currentSize
                  #fallback = currentFallback # same fallback solution but benchmarked at current problem size
                  fallbackLowerBoundP = currentFallback[0]
                  #fallbackSolution = fallback[1]
                  #fallbackTime = fallback[2]
                  #fallbackGFlops = self.getGFlops(fallbackProblem, fallbackTime)
                  continue
              else:
                # fallback is fastest at this size also
                if self.printLogic: print "STATUS - fallback is fastest at size %u*%u too" % (currentSize**0.5, currentSize**0.5)
                #fallbackSizeThreshold = currentSize
                fallbackLowerBoundP = currentFallback[0]
                #fallback = currentFallback # same fallback solution but benchmarked at current problem size
                #fallbackProblem = fallback[0]
                #fallbackSolution = fallback[1]
                #fallbackTime = fallback[2]
                #fallbackGFlops = self.getGFlops(fallbackProblem, fallbackTime)
                continue
            else:
              continue # to to find smaller size
        #else:
          # no fallback, so it's "valid" all the way down to zero
          #fallbackSizeThreshold = 0
        
        size = fallbackLowerBoundP.getSizeFree()**0.5
        pspString = self.pspToString(fallback)
        if self.printLogic: print "STATUS - fallback is fastest down to size %u*%u %s" % (size, size, pspString)
        
        #########################################################################
        # (c) at the largest size make list of all psps which are faster
        # than the fallback; logically all must be branch.multiple AND exact
        # match (else would be fallback); sorted fastest to slowest
        #########################################################################
        singletonsForLargestSize = self.getSingletons(pspsForLargestSize)
        singletonsFasterThanFallbackUnsorted = self.getPSPsFasterThan(singletonsForLargestSize, fallback)
        singletonsFasterThanFallback = self.sortSpeedPSPs(singletonsFasterThanFallbackUnsorted)
        singletonsFasterThanFallback = self.removeTileDuplicates( singletonsFasterThanFallback ) # if same tile but differet unrolls, remove slower
        #for psp in singletonsFasterThanFallback:
          #print "~" + self.pspToString(psp)
        
        #########################################################################
        # (d): (b) and (c) constitute the "rule"
        #########################################################################
        unorderedGroups = []
        for psp in singletonsFasterThanFallback:
          unorderedGroup = []
          unorderedGroup.append( psp )
          unorderedGroups.append( unorderedGroup )
          #print self.pspToString(psp) + " - adding tiles in original rule"
          fastestPSPs.add( tuple(copy.deepcopy(psp)) )
        rule = [unorderedGroups, fallback, ruleSizeThresholdUpperP, fallbackLowerBoundP]
        ruleString = self.ruleToString(rule)
        if self.printLogic: print "RULE: " + ruleString

        # if len(singletonsFasterThanFallback):
          # find size threshold of rule
          # (f) incrementally move down in size to fallback-threshold, at each size make sorted list of all singletons faster than fallback
        indexOfNextLargestSize = self.getIndexOfNextLargestSize(rangePSPs, fallback[0])
        if indexOfNextLargestSize < len(rangePSPs):
          nextLargestSizeP = rangePSPs[indexOfNextLargestSize][0]
          #print "%u >= %u" % (nextLargestSizeP.getSizeFree()**0.5, fallbackLowerBoundP.getSizeFree()**0.5)
          while self.compareSize(nextLargestSizeP, fallbackLowerBoundP) >= 0:
            #print "checking size " + str(self.getSize(nextLargestSizeP)**(1.0/2.0))
            #print "singletonsForCurrentSize"
            singletonsForCurrentSize = self.getPSPsForSize(rangePSPs, nextLargestSizeP)
            #print "singletonsFasterThanFallbackCurrentSizeUnsorted"
            singletonsFasterThanFallbackCurrentSizeUnsorted = self.getPSPsFasterThan(singletonsForCurrentSize, fallback)
            #print "singletonsFasterThanFallbackCurrentSize"
            singletonsFasterThanFallbackCurrentSize = self.sortSpeedPSPs(singletonsFasterThanFallbackCurrentSizeUnsorted)
            #print "singletonsFasterThanFallbackCurrentSize remove duplicates"
            singletonsFasterThanFallbackCurrentSize = self.removeTileDuplicates( singletonsFasterThanFallbackCurrentSize )
            #print "creating new ugs"
            unorderedGroups = []
            for psp in singletonsFasterThanFallbackCurrentSize:
              unorderedGroup = []
              unorderedGroup.append( psp )
              unorderedGroups.append( unorderedGroup )
              #print self.pspToString(psp) + " - adding tiles in new rule"
              fastestPSPs.add( tuple(copy.deepcopy(psp)) )
            #print "creating new rule"
            newRule = [unorderedGroups, fallback, ruleSizeThresholdUpperP, nextLargestSizeP]
            newRuleString = self.ruleToString(newRule)
            if self.printLogic: print "NEXT RULE: " + newRuleString

            if self.rulesConflict(rule, newRule):
              if self.printLogic: print "STATUS - NEXT RULE REJECTED"
              # current rule is "the rule" with correct size threshold and correct
              break
            else:
              if self.printLogic: print "STATUS - NEXT RULE ACCEPTED (MERGING)"
              # we can make new rule which is at smaller size then "the rule" and may add more tiles without losing performance
              self.mergeRules(rule, newRule)
              ruleString = self.ruleToString(rule)
              if self.printLogic: print "MERGED RULE: " + ruleString
            #print "getting index of next largest size"
            indexOfNextLargestSize = self.getIndexOfNextLargestSize(rangePSPs, nextLargestSizeP)
            if indexOfNextLargestSize == len(rangePSPs):
              break
            #print "getting index of next largest size - done"
            nextLargestSizeP = rangePSPs[indexOfNextLargestSize][0]
            #print "continuing while"
          if self.printLogic: print "STATUS - Done scanning down sizes to find lowest size for rule"

        # (g) if (f) conflicts with (e) by more than tolerance, then this is the size threshold for rule
        # repeat (e) and (g)
        #else:
        #  # fallback is size threshold
        #  print "ERROR"
        #  rule.append(fallbackProblem)

        # remove duplicates in the rule one last time
        # rule[0] = self.removeTileDuplicates(rule[0])

        #######################
        # here is the rule
        #######################
        lastSizeGroup = self.getIndexOfNextLargestSize(rangePSPs, rule[3]) == len(rangePSPs)
        exactPSPsInRange = self.getPSPsLargerOrEqual(exactPSPs, rule[3])
        fastestExactPSPsInRange = []
        # for each unique problem, get only fastest
        iterCnt = 0
        #print "total = %u exact psps" % len(exactPSPsInRange)
        while len(exactPSPsInRange) > 0:
          iterCnt += 1
          if iterCnt > 20:
            break
          #print "new problem"
          problem = exactPSPsInRange[0][0]
          fastestTime  = 1e9
          fastestIndex = -1
          slowPSPs = []

          for i in range(0, len(exactPSPsInRange)):
            psp = exactPSPsInRange[i]
            if psp[0] == problem:
              time = psp[2]
              if time < fastestTime:
                #print "new fastest solution"
                fastestTime = time
                if fastestIndex >= 0:
                  slowPSPs.append(exactPSPsInRange[fastestIndex])
                fastestIndex = i
              else:
                slowPSPs.append(psp)
            #else:
              #print "problem not match"
          #print "%u slow psps" % len(slowPSPs)
          fastestExactPSPsInRange.append(exactPSPsInRange[fastestIndex])
          exactPSPsInRange.remove(exactPSPsInRange[fastestIndex])
          for slowPSP in slowPSPs:
            exactPSPsInRange.remove(slowPSP)
        for psp in fastestExactPSPsInRange:
          localSolutionSet.add( psp[1] )

        finalRuleString = self.ruleToString(rule)
        if self.printLogic: print "FINAL RULE: " + finalRuleString
        self.addRuleToSets(rule)
        s += self.ruleToLibString(rule, firstSizeGroup, lastSizeGroup, fastestExactPSPsInRange, "  ")
        for ug in rule[0]: # exact tiles
          for psp in ug:
            localSolutionSet.add( psp[1] )
            #print self.pspToString(psp) + " - adding tiles in final rule"
            fastestPSPs.add( tuple(copy.deepcopy(psp)) )
        for psp in fastestExactPSPsInRange:
          #print self.pspToString(psp) + " - adding unusuals in final rule"
          fastestPSPs.add( tuple(copy.deepcopy(psp)) )
        #print self.pspToString(rule[1]) + " - adding fallback of final rule"
        fastestPSPs.add( tuple(copy.deepcopy(rule[1])) )

        localSolutionSet.add(rule[1][1])
        newFallbackSolution = copy.deepcopy( rule[1][1] )
        #for i in range( 0, 4):
        #  if newFallbackSolution.kernels[i] != None:
        #    newFallbackSolution.kernels[i].unrolls = [ 1 ]
        #localSolutionSet.add(newFallbackSolution)

        # (h) remove psps which have size greater than rule-threshold
        rangeSizeBefore = len(rangePSPs)
        exactSizeBefore = len(exactPSPs)

        self.removePSPsLargerOrEqual(rangePSPs, rule[3])
        self.removePSPsLargerOrEqual(exactPSPs, rule[3])
        ruleSize = rule[3].getSizeFree()**0.5
        rangeSizeAfter = len(rangePSPs)
        exactSizeAfter = len(exactPSPs)
        if self.printLogic: print "STATUS - # PSPs after removing >= %u*%u: range=%u->%u; exact=%u->%u" % (ruleSize, ruleSize, rangeSizeBefore, rangeSizeAfter, exactSizeBefore, exactSizeAfter)

        #print "Rule DONE"
        firstSizeGroup = False
        
        # END WHILE

    

    s += "\n"
    s += "  return new Cobalt::%s%s( problem ); // fallback for k < UNROLL\n" % (self.solutionWriter.getName(self.fallbackPSPU1[1]), self.solutionWriter.getTemplateArgList(self.fallbackPSPU1[1]))
    s += "}\n"

    # prepend includes
    inc = "#include \"Problem.h\"\n"
    inc += "#include \"CobaltGetSolution_" + exactMatch.libString() + ".h\"\n"
    for solution in localSolutionSet:
      inc += "#include \"" + self.solutionWriter.getName(solution) + ".h\"\n"
    inc += "\n"
    s = inc + s

    # header file
    h += "#ifndef COBALT_" + functionName.upper() + "_H\n"
    h += "#define COBALT_" + functionName.upper() + "_H\n"
    h += "\n"
    h += "#include \"Cobalt.h\"\n"
    h += "#include \"Solution.h\"\n"
    h += "\n"
    h += "Cobalt::Solution* " + functionName + "( const Cobalt::Problem & problem, CobaltStatus *status);\n"
    h += "\n"
    h += "#endif\n"
    h += "\n"


    return (s, h, fastestPSPs)

  
  #############################################################################
  # write cmake file for CobaltLib solution selection
  #############################################################################
  def writeCobaltLibCMake(self, subdirectory):
    s = "# CobaltLib.cmake\n"
    s += "\n"
    s += "include( ${CobaltLib_KernelFiles_CMAKE_DYNAMIC} )\n"
    s += "include( ${CobaltLib_SolutionFiles_CMAKE_DYNAMIC} )\n"
    s += "\n"
    s += "set( CobaltLib_OtherFiles_GENERATED_DYNAMIC\n"
    
    for deviceProfile, exactMatches in self.psMap.iteritems():
      #print str(deviceProfile), str(exactMatches)
      # (2) Write Device-Level Solution Selection files
      baseName = "CobaltGetSolution_" + deviceProfile.libString()
      s += "  ${CobaltLib_DIR_GENERATED}" + subdirectory + baseName + ".cpp\n"
      s += "  ${CobaltLib_DIR_GENERATED}" + subdirectory + baseName + ".h\n"

      for exactMatch, pspTypes in exactMatches.iteritems():
        baseName = "CobaltGetSolution_" + exactMatch.libString()
        s += "  ${CobaltLib_DIR_GENERATED}" + subdirectory + baseName + ".cpp\n"
        s += "  ${CobaltLib_DIR_GENERATED}" + subdirectory + baseName + ".h\n"
    s += ")\n"
    s += "\n"
    s += "source_group(CobaltGen\\\\Other FILES\n"
    s += "  ${CobaltLib_OtherFiles_GENERATED_DYNAMIC} )\n"
    s += "\n"
    return s



  
  #############################################################################
  # write the benchmark data from xml's to csv format
  #############################################################################
  def writePSPsToCSV(self, exactMatch, inputPSPs):
    
    print "WritePSPtoCSV: sorting"
    pspsUnsorted = inputPSPs # copy.deepcopy(inputPSPs)
    psps = self.sortSizePSPs(pspsUnsorted)
    print "WritePSPtoCSV: done sorting"


    # in this routine, size is sqrted
    # set of all solutions "sorted" smallest to largest
    localSolutionSet = set()
    for psp in psps:
      localSolutionSet.add(psp[1])
    solutionList = list(localSolutionSet)
    solutionList = sorted(solutionList)
    
    pspMap = {}
    index = 0
    for solution in solutionList:
      pspMap[solution] = []
      pspMap[solution][:] = [psp  for psp in psps if psp[1] == solution]
      #print "pspMap[%u] size = %u" % (index, len(pspMap[solution]))
      index += 1

    s = ""
    # write row header
    s += "size, "

    # write column headers
    for solution in solutionList:
      s += self.solutionWriter.getName(solution) + ", "
    s += " <-- Fallbacks -- Tiles -->, "
    for solution in solutionList:
      s += self.solutionWriter.getName(solution) + ", "
    s += "\r"


    prevSize = 0
    while True:
      #print "prevSize = %u" % prevSize
      size = 1e6 # 1M*1M
      # get next larger size = smallest size that is still 2 larger than prev size
      for i in range( len(psps)-1, 0, -1):
        psp = psps[i]
        currentSize = psp[0].getSizeFree()**0.5
        if currentSize < size and currentSize > prevSize+2:
          size = currentSize
          #print "next size %u found at index %u" % (size, len(psps)-i)
          break
        psps.remove(psp)
      if size == 1e6:
        break
      # size should be mod16-1
      print "size = %u" % size
      # write row size
      s += str(size+1) + ", "
      # write solution speeds for fallbacks
      for solution in solutionList:
        pspFound = False
        for i in range(len(pspMap[solution])-1, 0, -1):
          #print i
          psp = pspMap[solution][i]
          if psp[1] == solution and int(psp[0].getSizeFree()**0.5) == size:
            pspFound = True
            s += str(self.getGFlops(psp[0], psp[2])) + ", "
            pspMap[solution].remove(psp) # after writing it, its no longer needed
            break
          # else:
          #   print "%f != %u" % (int(self.getSize(psp[0])**0.5), size)
        if not pspFound:
          s += " , "
      # write solution speeds for exact tiles
      size += 1
      s += " <-- Fallbacks -- Tiles -->, "
      for solution in solutionList:
        pspFound = False
        for i in range(len(pspMap[solution])-1, 0, -1):
          #print i
          psp = pspMap[solution][i]
          if psp[1] == solution and int(psp[0].getSizeFree()**0.5) == size:
            pspFound = True
            s += str(self.getGFlops(psp[0], psp[2])) + ", "
            pspMap[solution].remove(psp) # after writing it, its no longer needed
            break
        if not pspFound:
          s += " , "
      s += "\r"
      prevSize = size
    return s

  
  #############################################################################
  # reduce the number of solutions used by writeSolutionForExactMatch
  #############################################################################
  def pruneSolutions(self, exactMatch, rangePSPs, exactPSPs):
    # print "pruneSolutions( " + str(exactMatch) + " ); numPSPs=" + str(len(rangePSPs))
    # choose 1 unroll and wg/uT for each macro-tile/branch for rangePSPs
    # create set of macro-tile sizes
    uniqueSet = set() # only one solution per uniqueGroup will be kept
    uniqueDictionary = {}
    for psp in rangePSPs:
      tile0 = psp[1].kernels[0].tile.workGroup[0]*psp[1].kernels[0].tile.microTile[0]
      tile1 = psp[1].kernels[0].tile.workGroup[1]*psp[1].kernels[0].tile.microTile[1]
      branchType = psp[1].branch[0].value
      (size0, size1, sizeU) = psp[0].getSize01U()
      if size0%tile0==0 and size1%tile1==0:
        branchType = 0
      groupTuple = ( tile0, tile1, branchType, len( psp[1].kernels[0].unrolls) )
      uniqueSet.add( groupTuple )
      if groupTuple not in uniqueDictionary:
        uniqueDictionary[groupTuple] = list()
      uniqueDictionary[groupTuple].append( psp )
    # for each macro-tile/branch combo
    fastestSolutionForGroup = {}
    for uniqueGroup, psps in uniqueDictionary.iteritems():
      # print "  " + str(uniqueGroup) + ": " + str(len(psps))
      solutionPerf = {}
      for psp in psps:
        problem = psp[0]
        solution = psp[1]
        time = psp[2]
        if solution not in solutionPerf:
          solutionPerf[solution] = 0
        gFlops = (problem.getNumFlops()/1000000000.0) / (time/1000.0)
        solutionPerf[solution] += gFlops
      solutionPerfs = solutionPerf.items()
      fastestIdx = 0
      fastestPerf = -1
      for i in range(0, len(solutionPerfs)):
        (s,p) = solutionPerfs[i]
        if p > fastestPerf:
          fastestIdx = i
          fastestPerf = p
      (solution, perf) = solutionPerfs[fastestIdx]
      fastestSolutionForGroup[uniqueGroup] = solution
      #print "    fastest: " + str(solution)
    for psp in list(rangePSPs): #iterate over copy and remove from original
      tile0 = psp[1].kernels[0].tile.workGroup[0]*psp[1].kernels[0].tile.microTile[0]
      tile1 = psp[1].kernels[0].tile.workGroup[1]*psp[1].kernels[0].tile.microTile[1]
      branchType = psp[1].branch[0].value
      (size0, size1, sizeU) = psp[0].getSize01U()
      if size0%tile0==0 and size1%tile1==0:
        branchType = 0
      groupTuple = ( tile0, tile1, branchType, len( psp[1].kernels[0].unrolls) )
      if psp[1] != fastestSolutionForGroup[groupTuple]:
        rangePSPs.remove(psp)
    # print "finalPSPs=" + str(len(rangePSPs))



    