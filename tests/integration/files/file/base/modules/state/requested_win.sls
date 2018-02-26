count_root_dir_contents:
  cmd.run:
    - name: 'Get-ChildItem C:\\ | Measure-Object | %{$_.Count}'
    - shell: powershell
