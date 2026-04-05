import { type Table, flexRender } from "@tanstack/react-table";

export function TableRenderer<TData>(props: { table: Table<TData> }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          {props.table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} style={{ color: "var(--text-secondary)", fontSize: "12px", textTransform: "uppercase" }}>
              {headerGroup.headers.map((header) => (
                <th key={header.id} style={{ textAlign: "left", padding: "8px 0" }}>
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {props.table.getRowModel().rows.length === 0 ? (
            <tr>
              <td colSpan={Math.max(1, props.table.getAllLeafColumns().length)} style={{ padding: "12px 0", color: "var(--text-secondary)" }}>
                Không có dữ liệu
              </td>
            </tr>
          ) : (
            props.table.getRowModel().rows.map((row) => (
              <tr key={row.id} style={{ borderTop: "1px solid var(--border-default)" }}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} style={{ padding: "10px 0", color: "var(--text-primary)" }}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
