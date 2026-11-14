import os
from pathlib import Path
import stat
import tempfile
import unittest

from jev.backup import create_key, write_new


class PrivateFileTests(unittest.TestCase):
    def test_new_file_is_private_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'key.jevkey'
            create_key(path)
            self.assertEqual(len(path.read_bytes()),32)
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_new(path,b'overwrite')
            self.assertEqual(path.read_bytes(),before)
            if os.name != 'nt':
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows DACL test')
    def test_windows_file_has_only_current_user_access_without_inheritance(self):
        import ctypes
        from ctypes import wintypes
        from jev.private_file import _windows_user_sid
        advapi = ctypes.WinDLL('advapi32',use_last_error=True)
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        advapi.GetFileSecurityW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,
                                          ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
        advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
            ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(wintypes.LPWSTR),ctypes.c_void_p]
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'özel anahtar.jevkey'
            create_key(path)
            size = wintypes.DWORD()
            advapi.GetFileSecurityW(str(path),4,None,0,ctypes.byref(size))
            buf = ctypes.create_string_buffer(size.value)
            self.assertTrue(advapi.GetFileSecurityW(str(path),4,buf,size,ctypes.byref(size)))
            text = wintypes.LPWSTR()
            self.assertTrue(advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW(buf,1,4,ctypes.byref(text),None))
            try:
                sddl = text.value
                self.assertIn('D:P',sddl)
                self.assertEqual(sddl.count('(A;'),1)
                # SDDL yerel Administrator SID'ini LA takma adıyla gösterebilir.
                # Metin yerine ACE içindeki gerçek SID'i karşılaştır.
                advapi.GetSecurityDescriptorDacl.argtypes = [ctypes.c_void_p,
                    ctypes.POINTER(wintypes.BOOL),ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.BOOL)]
                advapi.GetAce.argtypes = [ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p)]
                advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p,ctypes.POINTER(wintypes.LPWSTR)]
                present,defaulted = wintypes.BOOL(),wintypes.BOOL()
                dacl,ace = ctypes.c_void_p(),ctypes.c_void_p()
                self.assertTrue(advapi.GetSecurityDescriptorDacl(buf,ctypes.byref(present),ctypes.byref(dacl),ctypes.byref(defaulted)))
                self.assertTrue(present.value)
                self.assertTrue(advapi.GetAce(dacl,0,ctypes.byref(ace)))
                actual_sid = wintypes.LPWSTR()
                self.assertTrue(advapi.ConvertSidToStringSidW(ctypes.c_void_p(ace.value+8),ctypes.byref(actual_sid)))
                try:
                    self.assertEqual(actual_sid.value,_windows_user_sid())
                finally:
                    kernel.LocalFree(ctypes.cast(actual_sid,ctypes.c_void_p))
            finally:
                kernel.LocalFree(ctypes.cast(text,ctypes.c_void_p))
