# export QT_SCALE_FACTOR=1
export QT_STYLE_OVERRIDE=fusion
# allows the virtual keyboard to be drawn within eglfs
export QT_QUICK_BACKEND=software
if [ -z "$QT_QPA_PLATFORM" ]; then
    export QT_QPA_PLATFORM=eglfs
    export QT_QPA_EGLFS_HIDECURSOR=1
    export QT_QPA_EGLFS_INTEGRATION=eglfs_kms
    export QT_QPA_EGLFS_ROTATION=-90
    export QT_QPA_EGLFS_KMS_ATOMIC=1
    # export QT_QPA_EGLFS_PHYSICAL_WIDTH=110
    # export QT_QPA_EGLFS_PHYSICAL_HEIGHT=62
    export QT_QPA_EGLFS_PHYSICAL_WIDTH=176
    export QT_QPA_EGLFS_PHYSICAL_HEIGHT=99
fi
