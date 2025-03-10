#!/bin/env python3
#
# Copyright (C) 2021-2023 The LineageOS Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import common
import re

def FullOTA_InstallBegin(info):
  if info.info_dict.get("vendor.build.prop").GetProp("ro.board.platform") != "universal9825_r":
    AddImage(info, "super_empty.img", "/tmp/super_empty.img", False);
    info.script.AppendExtra('exynos9820.retrofit_dynamic_partitions();')
  return

def FullOTA_InstallEnd(info):
  OTA_InstallEnd(info)
  return

def IncrementalOTA_InstallEnd(info):
  info.input_zip = info.target_zip
  OTA_InstallEnd(info)
  return

def AddImage(info, basename, dest, printInfo=True):
  data = info.input_zip.read("IMAGES/" + basename)
  common.ZipWriteStr(info.output_zip, basename, data)
  if printInfo:
    info.script.Print("Patching {} image unconditionally...".format(dest.split('/')[-1]))
  info.script.AppendExtra('package_extract_file("%s", "%s");' % (basename, dest))

def AddFirmwareImage(info, model, basename, dest, simple=False, offset=8):
  if ("RADIO/%s_%s" % (basename, model)) in info.input_zip.namelist():
    data = info.input_zip.read("RADIO/%s_%s" % (basename, model))
    common.ZipWriteStr(info.output_zip, "firmware/%s/%s" % (model, basename), data);
    info.script.Print("Patching {} image unconditionally...".format(basename.split('.')[0]));
    if simple:
      info.script.AppendExtra('package_extract_file("firmware/%s/%s", "%s");' % (model, basename, dest))
    else:
      uses_single_bota = dest == "/dev/block/by-name/bota"
      size = info.input_zip.getinfo("RADIO/%s_%s" % (basename, model)).file_size
      if not uses_single_bota:
        info.script.AppendExtra('assert(exynos9820.mark_header_bt("%s", 0, 0, 0));' % dest);
      info.script.AppendExtra('assert(exynos9820.write_data_bt("firmware/%s/%s", "%s", %d, %d));' % (model, basename, dest, offset, size))
      if not uses_single_bota:
        info.script.AppendExtra('assert(exynos9820.mark_header_bt("%s", 0, 0, 3142939818));' % dest)
      return size
    return 0

def OTA_InstallEnd(info):
  if "IMAGES/dtb.img" in info.input_zip.namelist():
    AddImage(info, "dtb.img", "/dev/block/by-name/dtb")
  AddImage(info, "dtbo.img", "/dev/block/by-name/dtbo")
  AddImage(info, "vbmeta.img", "/dev/block/by-name/vbmeta")

  if "RADIO/models" in info.input_zip.namelist():
    modelsIncluded = []
    for model in info.input_zip.read("RADIO/models").decode('utf-8').splitlines():
      if "RADIO/version_%s" % model in info.input_zip.namelist():
        modelsIncluded.append(model)
        version = info.input_zip.read("RADIO/version_%s" % model).decode('utf-8').splitlines()[0]
        info.script.AppendExtra('# Firmware update to %s for %s' % (version, model))
        info.script.AppendExtra('ifelse (getprop("ro.boot.em.model") == "%s" &&' % model)
        info.script.AppendExtra('exynos9820.verify_no_downgrade("%s") == "0" &&' % version)
        info.script.AppendExtra('getprop("ro.boot.bootloader") != "%s",' % version)
        if info.info_dict.get("vendor.build.prop").GetProp("ro.board.platform") != "universal9825_r":
          info.script.Print('Updating firmware to %s for %s' % (version, model))
          AddFirmwareImage(info, model, "sboot.bin", "/dev/block/by-name/bota0")
          AddFirmwareImage(info, model, "cm.bin", "/dev/block/by-name/bota1")
          AddFirmwareImage(info, model, "up_param.bin", "/dev/block/by-name/bota2")
          AddFirmwareImage(info, model, "keystorage.bin", "/dev/block/by-name/keystorage", True)
          AddFirmwareImage(info, model, "uh.bin", "/dev/block/by-name/uh", True)
        else:
          offset = 8
          numImages = 0
          info.script.AppendExtra('assert(exynos9820.mark_header_bt("/dev/block/by-name/bota", 0, 0, 0));')
          for image in 'cm.bin', 'keystorage.bin', 'sboot.bin', 'uh.bin', 'up_param.bin':
            size = AddFirmwareImage(info, model, image, "/dev/block/by-name/bota", False, offset)
            if size > 0:
              numImages += 1
              offset += size + 36 # header size
          info.script.AppendExtra('assert(exynos9820.mark_header_bt("/dev/block/by-name/bota", 0, %d, 3142939818));' % numImages)
        AddFirmwareImage(info, model, "modem.bin", "/dev/block/by-name/radio", True)
        AddFirmwareImage(info, model, "modem_5g.bin", "/dev/block/by-name/radio2", True)
        AddFirmwareImage(info, model, "modem_debug.bin", "/dev/block/by-name/cp_debug", True)
        AddFirmwareImage(info, model, "modem_debug_5g.bin", "/dev/block/by-name/cp2_debug", True)
        AddFirmwareImage(info, model, "dqmdbg.img", "/dev/block/by-name/dqmdbg", True)
        AddFirmwareImage(info, model, "param.bin", "/dev/block/by-name/param", True)
        info.script.AppendExtra(',"");')

    modelCheck = ""
    for model in modelsIncluded:
      if len(modelCheck) > 0:
        modelCheck += ' || '
      modelCheck += 'getprop("ro.boot.em.model") == "%s"' % model
    if len(modelCheck) > 0:
      info.script.AppendExtra('%s || abort("Unsupported model, not updating firmware!");' % modelCheck)
  return
