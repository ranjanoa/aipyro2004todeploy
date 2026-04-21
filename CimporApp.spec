# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('static', 'static')],
    hiddenimports=[
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
        'eventlet.hubs.poll',
        'dns.rdtypes.ANY',
        'dns.rdtypes.IN',
        'dns.rdtypes.MX',
        'dns.rdtypes.NS',
        'dns.rdtypes.SOA',
        'dns.rdtypes.TXT',
        'dns.rdtypes.AAAA',
        'dns.rdtypes.A',
        'engineio.async_drivers.eventlet',
        'importlib_metadata'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['files'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CimporApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
)
