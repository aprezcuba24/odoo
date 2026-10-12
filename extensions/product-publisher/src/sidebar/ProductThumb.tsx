type Props = {
  imageBase64: string | null
  imageMime: string | null
}

export function ProductThumb({ imageBase64, imageMime }: Props) {
  if (!imageBase64 || !imageMime) {
    return <div className="product-thumb" />
  }
  const src = `data:${imageMime};base64,${imageBase64}`
  return <img className="product-thumb" src={src} alt="" />
}
